"""Safe, additive variant management. Grocy remains authoritative for stock and barcodes.

The SQLite catalog is stored in the add-on's persistent app_config volume.
No stock movements, product merges or shopping-list writes occur here.
"""
import os
from decimal import Decimal, InvalidOperation
from contextlib import closing
from pathlib import Path

import barcode_stock
from generic_catalog import connect, register_generic, register_variant, resolve_barcode
from importer import grocy

CATALOG_DB = Path(os.environ.get("GENERIC_CATALOG_DB", "/config/generic_catalog.sqlite3"
                                 if os.environ.get("HA_INGRESS_MODE") == "1"
                                 else str(Path(__file__).resolve().parent / "runtime" / "generic_catalog.sqlite3")))


def variants_for_product(product_id):
    """Return local variants for one Grocy product, without changing Grocy."""
    with closing(connect(CATALOG_DB)) as db:
        rows = db.execute(
            "SELECT v.barcode, v.display_name, v.supermarket, v.brand, v.units_per_purchase "
            "FROM product_variants v JOIN generic_products g ON g.id=v.generic_id "
            "WHERE g.grocy_product_id=? ORDER BY v.display_name, v.barcode",
            (int(product_id),)).fetchall()
    return [dict(zip(("barcode", "name", "supermarket", "brand", "units_per_purchase"), row))
            for row in rows]


def save_variant(product_id, barcode, name, *, supermarket="", brand="", units_per_purchase="1"):
    """Audit both catalogs before writing metadata; never alter Grocy stock.

    If a barcode is new, register it with the *same* canonical Grocy product.
    If the subsequent local write fails, the barcode remains safely attached
    in Grocy and the operation can be retried. Never auto-consolidate products.
    """
    try:
        pid = int(product_id)
        quantity = Decimal(str(units_per_purchase))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("Producto o factor de compra no válido") from exc
    if pid <= 0 or not quantity.is_finite() or not Decimal("0") < quantity < Decimal("1000000"):
        raise ValueError("Producto o factor de compra no válido")
    barcode = barcode_stock.validate_barcode(barcode)
    name = str(name or "").strip()
    supermarket, brand = str(supermarket or "").strip(), str(brand or "").strip()
    if not name or len(name) > 200 or len(supermarket) > 120 or len(brand) > 120:
        raise ValueError("Indica un nombre de variante válido (máximo 200 caracteres)")

    product = grocy("GET", f"objects/products/{pid}")
    if not isinstance(product, dict) or int(product.get("id", 0)) != pid:
        raise ValueError("El producto genérico no existe en Grocy")

    with closing(connect(CATALOG_DB)) as db:
        local = resolve_barcode(db, barcode)
        if local and int(local["grocy_product_id"]) != pid:
            raise ValueError("Este código ya pertenece a otro genérico")
        rows = grocy("GET", "objects/product_barcodes")
        if not isinstance(rows, list):
            raise ValueError("No se pudo auditar los códigos de Grocy")
        owners = {int(row["product_id"]) for row in rows if str(row.get("barcode")) == barcode}
        if owners - {pid}:
            raise ValueError("Este código pertenece a otro producto en Grocy")
        if not owners:
            barcode_stock.associate_product_barcode(pid, barcode)
            # Recheck the authoritative source before saving local metadata.
            rows = grocy("GET", "objects/product_barcodes")
            owners = {int(row["product_id"]) for row in rows if str(row.get("barcode")) == barcode}
            if owners != {pid}:
                raise ValueError("No se pudo verificar la asociación del código en Grocy")
        gid = register_generic(db, pid, str(product["name"]))
        register_variant(db, gid, barcode, name, supermarket=supermarket, brand=brand,
                         units_per_purchase=float(quantity), grocy_barcode_owners=owners)
    return {"product_id": pid, "barcode": barcode, "name": name}
