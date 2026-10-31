"""Read-only migration audit. Export before considering any product consolidation."""
from collections import defaultdict
from contextlib import closing
from decimal import Decimal, InvalidOperation

from generic_catalog import connect
from importer import grocy
from variant_catalog import CATALOG_DB


def build_snapshot():
    """Collect Grocy identifiers, units, stock, barcodes and shopping references.

    This function only performs GET requests. It never merges, deletes, adjusts
    stock or changes Alexa checkpoints. The JSON output is for human review.
    """
    products = grocy("GET", "objects/products")
    barcodes = grocy("GET", "objects/product_barcodes")
    stock = grocy("GET", "stock")
    shopping = grocy("GET", "objects/shopping_list")
    units = grocy("GET", "objects/quantity_units")
    if not all(isinstance(value, list) for value in (products, barcodes, stock, shopping, units)):
        raise ValueError("Grocy returned an incomplete catalog audit")
    unit_names = {int(row["id"]): str(row["name"]) for row in units}
    owners = defaultdict(set)
    by_product = defaultdict(list)
    for row in barcodes:
        code = str(row["barcode"])
        pid = int(row["product_id"])
        owners[code].add(pid)
        by_product[pid].append(code)
    stock_by_id = {}
    for row in stock:
        pid = int(row["product_id"])
        try:
            amount = Decimal(str(row["amount"]))
        except InvalidOperation as exc:
            raise ValueError("Invalid stock amount in Grocy audit") from exc
        if not amount.is_finite() or pid in stock_by_id:
            raise ValueError("Invalid or duplicate stock amount in Grocy audit")
        stock_by_id[pid] = format(amount, "f")
    shopping_by_product = defaultdict(list)
    for row in shopping:
        pid = int(row.get("product_id") or 0)
        if pid:
            shopping_by_product[pid].append(int(row["id"]))
    with closing(connect(CATALOG_DB)) as db:
        variants = db.execute(
            "SELECT g.grocy_product_id, v.barcode, v.display_name, "
            "v.supermarket, v.brand, v.units_per_purchase "
            "FROM product_variants v JOIN generic_products g ON g.id=v.generic_id "
            "ORDER BY g.grocy_product_id, v.barcode").fetchall()
    variants_by_product = defaultdict(list)
    conflicts = []
    for pid, code, name, supermarket, brand, factor in variants:
        variants_by_product[pid].append({
            "barcode": code, "name": name, "supermarket": supermarket,
            "brand": brand, "units_per_purchase": factor})
        if owners.get(code) != {pid}:
            conflicts.append({"barcode": code, "local_product_id": pid,
                              "grocy_product_ids": sorted(owners.get(code, set()))})
    for code, pids in owners.items():
        if len(pids) > 1:
            conflicts.append({"barcode": code, "grocy_product_ids": sorted(pids),
                              "issue": "barcode_owned_by_multiple_products"})
    result = []
    known = set()
    for p in products:
        pid = int(p["id"])
        if pid in known:
            raise ValueError("Duplicate product ID in Grocy audit")
        known.add(pid)
        stock_unit = int(p.get("qu_id_stock") or 0)
        purchase_unit = int(p.get("qu_id_purchase") or stock_unit)
        result.append({
            "id": pid, "name": str(p["name"]),
            "stock_amount": stock_by_id.get(pid, "0"),
            "stock_unit_id": stock_unit, "stock_unit": unit_names.get(stock_unit, ""),
            "purchase_unit_id": purchase_unit, "purchase_unit": unit_names.get(purchase_unit, ""),
            "purchase_to_stock_factor": p.get("qu_factor_purchase_to_stock"),
            "barcodes": sorted(by_product.get(pid, [])),
            "shopping_entry_ids": sorted(shopping_by_product.get(pid, [])),
            "variants": variants_by_product.get(pid, []),
        })
    for pid in variants_by_product:
        if pid not in known:
            conflicts.append({"local_product_id": pid, "issue": "canonical_product_missing"})
    return {"schema_version": 1, "source": "Grocy (solo lectura)",
            "products": sorted(result, key=lambda p: p["id"]),
            "barcode_conflicts": conflicts,
            "unlinked_shopping_entries": [
                int(row["id"]) for row in shopping
                if int(row.get("product_id") or 0) not in known
                and int(row.get("product_id") or 0) != 0],
            "shopping_notes": [
                {"id": int(row["id"]), "note": str(row.get("note") or "")}
                for row in shopping if not int(row.get("product_id") or 0)],
            "requires_explicit_approval_for_merges": True}
