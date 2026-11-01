"""Reversible product lifecycle. Never consume stock or delete Grocy history."""
from decimal import Decimal
import barcode_stock


def is_active(product):
    return barcode_stock._done(product.get("active", True))


def set_active(product_id, expected_name, active):
    pid = int(product_id)
    product = barcode_stock.grocy("GET", f"objects/products/{pid}")
    if not isinstance(product, dict) or product.get("name") != expected_name:
        raise barcode_stock.BarcodeError("El producto ha cambiado. Actualiza la ficha")
    if not active:
        stock = barcode_stock.grocy("GET", f"stock/products/{pid}")
        amount = Decimal(str(stock["stock_amount"]))
        if not amount.is_finite() or amount != 0:
            raise barcode_stock.BarcodeError("Solo se puede archivar un producto sin existencias")
        # Preserve historical links, but refuse to hide an active dependency.
        for collection, field in (("shopping_list", "product_id"), ("recipes_pos", "product_id"),
                                  ("recipes", "product_id"), ("products", "parent_product_id"),
                                  ("meal_plan", "product_id")):
            rows = barcode_stock.grocy("GET", "objects/" + collection)
            if not isinstance(rows, list):
                raise barcode_stock.BarcodeError("No se pudieron comprobar las referencias del producto")
            if any(str(row.get(field)) == str(pid) for row in rows):
                labels = {"shopping_list": "lista de la compra", "recipes_pos": "recetas", "recipes": "recetas", "products": "productos dependientes", "meal_plan": "plan de comidas"}
                raise barcode_stock.BarcodeError("El producto sigue en uso: " + labels[collection])
    barcode_stock.grocy("PUT", f"objects/products/{pid}", {"active": 1 if active else 0})
    saved = barcode_stock.grocy("GET", f"objects/products/{pid}")
    if is_active(saved) != active:
        raise RuntimeError("No se pudo verificar el estado del producto")
    return {"product_id": pid, "active": active}


def archived_inventory():
    products = barcode_stock.grocy("GET", "objects/products")
    if not isinstance(products, list):
        raise barcode_stock.BarcodeError("No se pudo consultar el catálogo")
    ids = {int(p["id"]) for p in products if not is_active(p)}
    return [{**row, "shopping_amount": "0", "shopping_step": "1", "shopping_unit": row["unit"],
             "shopping_can_subtract": False} for row in barcode_stock.inventory_snapshot(include_archived=True)
            if row["id"] in ids]
