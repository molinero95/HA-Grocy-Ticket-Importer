"""Stock changes via barcode. Product catalog entries are never deleted."""
import re
from decimal import Decimal

from importer import grocy

BARCODE_RE = re.compile(r"^[0-9]{8,14}$")

class BarcodeError(ValueError):
    pass

def validate_barcode(value):
    barcode = (value or "").strip()
    if not BARCODE_RE.fullmatch(barcode):
        raise BarcodeError("Introduce un código de barras numérico de 8 a 14 dígitos")
    return barcode

def find_product(barcode):
    barcode = validate_barcode(barcode)
    matches = [row for row in grocy("GET", "objects/product_barcodes")
               if str(row["barcode"]) == barcode]
    ids = {int(row["product_id"]) for row in matches}
    if len(ids) > 1:
        raise BarcodeError("El código está vinculado a varios productos; revísalo en Grocy")
    if not ids:
        return None
    pid = ids.pop()
    matches = [p for p in grocy("GET", "objects/products") if int(p["id"]) == pid]
    if len(matches) != 1:
        raise BarcodeError("El código referencia un producto inexistente")
    return matches[0]

def list_products():
    """Return existing catalog choices, without changing stock."""
    return sorted(
        [{"id": int(p["id"]), "name": str(p["name"])}
         for p in grocy("GET", "objects/products")],
        key=lambda p: (p["name"].casefold(), p["id"]),
    )

def associate_barcode(barcode, product_id):
    """Link barcode to an existing product. Does not create stock movements."""
    barcode = validate_barcode(barcode)
    try:
        product_id = int(product_id)
    except (TypeError, ValueError) as exc:
        raise BarcodeError("Selecciona un producto válido") from exc
    if product_id <= 0:
        raise BarcodeError("Selecciona un producto válido")
    products = [p for p in list_products() if p["id"] == product_id]
    if len(products) != 1:
        raise BarcodeError("El producto elegido no existe")
    existing = find_product(barcode)
    if existing is not None:
        if int(existing["id"]) == product_id:
            return {"product_id": product_id, "name": products[0]["name"], "already_linked": True}
        raise BarcodeError("Este código ya pertenece a otro producto. No se ha modificado nada")
    grocy("POST", "objects/product_barcodes",
          {"product_id": product_id, "barcode": barcode})
    return {"product_id": product_id, "name": products[0]["name"], "already_linked": False}

def _get_name_and_id(barcode):
    product = find_product(barcode)
    if product is None:
        raise BarcodeError("No existe un producto con este código")
    return product["name"], int(product["id"])

def add_one(barcode, name="", location_id=2, unit_id=2):
    """Create a product if missing, associate barcode, then increase stock by one."""
    barcode = validate_barcode(barcode)
    product = find_product(barcode)
    created = False
    if product is None:
        name = name.strip()
        if not name or len(name) > 200:
            raise BarcodeError("Indica el nombre del nuevo producto (máx. 200 caracteres)")
        existing = [p for p in grocy("GET", "objects/products")
                    if p["name"].strip().casefold() == name.casefold()]
        if existing:
            raise BarcodeError("Ya existe un producto con ese nombre. Asocia su código en Grocy antes de continuar")
        payload = {"name": name, "location_id": int(location_id),
                   "qu_id_stock": int(unit_id), "qu_id_purchase": int(unit_id),
                   "min_stock_amount": 0}
        result = grocy("POST", "objects/products", payload)
        pid = int(result["created_object_id"])
        # If barcode association fails, do not retry blindly: product already exists.
        grocy("POST", "objects/product_barcodes", {"product_id": pid, "barcode": barcode})
        created = True
    else:
        pid = int(product["id"])
        if int(product["qu_id_stock"]) != int(unit_id):
            # "One" means one stock unit, regardless of which unit is configured.
            pass
    grocy("POST", f"stock/products/{pid}/add",
          {"amount": 1, "price": 0, "best_before_date": "2999-12-31",
           "location_id": int(location_id), "note": "Alta manual por código de barras"})
    return {"product_id": pid, "created": created}

def remove_one(barcode):
    """Consume exactly one stock unit, preserving the product in the catalog."""
    name, pid = _get_name_and_id(barcode)
    details = grocy("GET", f"stock/products/{pid}")
    amount = Decimal(str(details.get("stock_amount", 0)))
    if amount < 1:
        raise BarcodeError("El producto no tiene una unidad completa disponible en stock")
    grocy("POST", f"stock/products/{pid}/consume", {"amount": 1, "spoiled": False})
    return {"product_id": pid, "name": name}
