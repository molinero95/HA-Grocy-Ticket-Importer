"""Grocy 4.x purchase conversion contract; never rewrite existing inventory.

Reference: grocy/grocy services/StockService.php, ExternalBarcodeLookup:
conversions live in objects/quantity_unit_conversions, not writable product fields.
"""
from decimal import Decimal


def purchase_factor(grocy, product_id, purchase_id, stock_id):
    if int(purchase_id) == int(stock_id):
        return Decimal(1)
    rows = grocy("GET", "objects/quantity_unit_conversions")
    if not isinstance(rows, list):
        raise ValueError("No se pudieron verificar las conversiones de Grocy")
    direct = [row for row in rows if int(row["from_qu_id"]) == int(purchase_id) and int(row["to_qu_id"]) == int(stock_id)]
    specific = [row for row in direct if row.get("product_id") not in (None, "") and int(row["product_id"]) == int(product_id)]
    inherited = [row for row in direct if row.get("product_id") in (None, "")]
    selected = specific or inherited
    if len(selected) != 1:
        raise ValueError("La conversión de compra no es única; revísala en Grocy")
    factor = Decimal(str(selected[0]["factor"]))
    if not factor.is_finite() or factor <= 0:
        raise ValueError("Factor de compra no válido")
    return factor


def create_purchase_conversion(grocy, product_id, purchase_id, stock_id, factor):
    """Only called after creating a new product, before any initial stock write."""
    grocy("POST", "objects/quantity_unit_conversions", {
        "product_id": int(product_id), "from_qu_id": int(purchase_id),
        "to_qu_id": int(stock_id), "factor": int(factor),
    })
    if purchase_factor(grocy, product_id, purchase_id, stock_id) != Decimal(str(factor)):
        raise ValueError("Grocy no confirmó el factor de compra; no se añaden existencias")
