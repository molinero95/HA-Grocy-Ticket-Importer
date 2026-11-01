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
    """Set and verify a new product conversion before its initial stock write."""
    rows = grocy("GET", "objects/quantity_unit_conversions")
    if not isinstance(rows, list):
        raise ValueError("No se pudieron verificar las conversiones de Grocy")
    existing = [row for row in rows if str(row.get("product_id")) == str(product_id)
                and int(row["from_qu_id"]) == int(purchase_id) and int(row["to_qu_id"]) == int(stock_id)]
    if len(existing) > 1:
        raise ValueError("La conversión de compra está duplicada")
    if existing:
        # Grocy 4.7 creates factor-1 conversions automatically with a product.
        if Decimal(str(existing[0]["factor"])) != Decimal(str(factor)):
            grocy("PUT", "objects/quantity_unit_conversions/" + str(int(existing[0]["id"])), {"factor": int(factor)})
    else:
        grocy("POST", "objects/quantity_unit_conversions", {
            "product_id": int(product_id), "from_qu_id": int(purchase_id),
            "to_qu_id": int(stock_id), "factor": int(factor),
        })
    if purchase_factor(grocy, product_id, purchase_id, stock_id) != Decimal(str(factor)):
        raise ValueError("Grocy no confirmó el factor de compra; no se añaden existencias")


def update_purchase_configuration(grocy, product_id, purchase_id, factor, expected):
    """Edit only future purchase metadata; stock unit, lots and amounts are immutable."""
    pid, purchase_id = int(product_id), int(purchase_id)
    product = grocy("GET", f"objects/products/{pid}")
    stock_id = int(product["qu_id_stock"])
    current_purchase = int(product.get("qu_id_purchase") or stock_id)
    current_factor = purchase_factor(grocy, pid, current_purchase, stock_id)
    if (not isinstance(expected, dict) or int(expected.get("unit_id", 0)) != stock_id
            or int(expected.get("purchase_unit_id", 0)) != current_purchase
            or Decimal(str(expected.get("factor"))) != current_factor):
        raise ValueError("La configuración ha cambiado. Actualiza la ficha")
    units = {int(row["id"]): str(row["name"]).casefold() for row in grocy("GET", "objects/quantity_units")}
    amount = Decimal(str(factor))
    if not amount.is_finite() or amount != amount.to_integral_value() or not 1 <= amount <= 1000:
        raise ValueError("Las piezas por pack deben ser un entero entre 1 y 1000")
    if purchase_id != stock_id:
        if units.get(purchase_id) not in ("pack", "paquete", "envase") or units.get(stock_id) not in ("piece", "pieces", "unidad", "unidades"):
            raise ValueError("Pack solo se puede usar para comprar un producto cuyo stock está en piezas")
    elif amount != 1:
        raise ValueError("La unidad de stock tiene factor de compra 1")
    if current_purchase == purchase_id and current_factor == amount:
        return {"product_id": pid, "purchase_unit_id": purchase_id, "factor": str(amount)}
    shopping = grocy("GET", "objects/shopping_list")
    if not isinstance(shopping, list) or any(str(row.get("product_id")) == str(pid) for row in shopping):
        raise ValueError("Retira el producto de la lista antes de cambiar su configuración de compra")
    before = Decimal(str(grocy("GET", f"stock/products/{pid}")["stock_amount"]))
    if purchase_id != stock_id:
        rows = grocy("GET", "objects/quantity_unit_conversions")
        existing = [row for row in rows if str(row.get("product_id")) == str(pid) and int(row["from_qu_id"]) == purchase_id and int(row["to_qu_id"]) == stock_id]
        if len(existing) > 1:
            raise ValueError("Hay conversiones duplicadas; revísalas en Grocy")
        body = {"product_id": pid, "from_qu_id": purchase_id, "to_qu_id": stock_id, "factor": int(amount)}
        if existing:
            grocy("PUT", "objects/quantity_unit_conversions/" + str(int(existing[0]["id"])), body)
        else:
            grocy("POST", "objects/quantity_unit_conversions", body)
    grocy("PUT", f"objects/products/{pid}", {"qu_id_purchase": purchase_id})
    saved = grocy("GET", f"objects/products/{pid}")
    after = Decimal(str(grocy("GET", f"stock/products/{pid}")["stock_amount"]))
    if (int(saved["qu_id_stock"]) != stock_id or int(saved["qu_id_purchase"]) != purchase_id
            or purchase_factor(grocy, pid, purchase_id, stock_id) != amount or before != after):
        raise RuntimeError("No se pudo verificar la configuración. Comprueba Grocy")
    return {"product_id": pid, "purchase_unit_id": purchase_id, "factor": str(amount)}
