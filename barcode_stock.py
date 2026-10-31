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

PHOTO_MARKER = re.compile(r"(?:\n|^)\[Despensa: imagen=(https://images\.openfoodfacts\.org/[^\]\s]+)\]\s*")


def saved_photo(product):
    """Only show image URLs from the trusted Open Food Facts image host."""
    from product_images import safe_image_url
    match = PHOTO_MARKER.search(str(product.get("description") or ""))
    return safe_image_url(match.group(1)) if match else None


def save_product_photo(product_id, image_url):
    """Persist the discovered public image URL in Grocy product metadata."""
    from product_images import safe_image_url
    url = safe_image_url(image_url)
    if not url:
        raise BarcodeError("URL de imagen no permitida")
    pid = int(product_id)
    product = grocy("GET", f"objects/products/{pid}")
    if not isinstance(product, dict) or int(product.get("id") or 0) != pid:
        raise BarcodeError("Producto inexistente")
    description = PHOTO_MARKER.sub("", str(product.get("description") or "")).rstrip()
    description += ("\n" if description else "") + "[Despensa: imagen=" + url + "]"
    grocy("PUT", f"objects/products/{pid}", {"description": description})
    return url


def inventory_snapshot():
    """Read-only stock overview in three Grocy requests, not one per product.

    GET /stock returns the current stock for stocked products; catalog products
    absent from that response have zero stock. Any malformed response fails
    rather than incorrectly showing zero quantities.
    """
    products = grocy("GET", "objects/products")
    units_data = grocy("GET", "objects/quantity_units")
    current_stock = grocy("GET", "stock")
    if not all(isinstance(value, list) for value in (products, units_data, current_stock)):
        raise BarcodeError("Respuesta inesperada de Grocy al consultar el inventario")
    units = {int(unit["id"]): str(unit["name"]) for unit in units_data}
    stock_amounts = {}
    for entry in current_stock:
        pid = int(entry["product_id"])
        amount = Decimal(str(entry["amount"]))
        if not amount.is_finite():
            raise BarcodeError("Cantidad de stock no válida en Grocy")
        if pid in stock_amounts:
            raise BarcodeError("Grocy devolvió un producto duplicado en el stock")
        stock_amounts[pid] = amount
    rows = []
    for product in products:
        pid = int(product["id"])
        quantity = stock_amounts.get(pid, Decimal("0"))
        rows.append({
            "id": pid,
            "name": str(product["name"]),
            "image_url": saved_photo(product),
            "amount": format(quantity.quantize(Decimal("0.01")), "f").rstrip("0").rstrip(".") if quantity else "0",
            "unit": units.get(int(product.get("qu_id_stock") or 0), "ud. stock"),
        })
    return sorted(rows, key=lambda row: (row["name"].casefold(), row["id"]))


def inventory_with_shopping():
    """Combine pantry and current Grocy shopping list in stock units."""
    rows = inventory_snapshot()
    entries = grocy("GET", "objects/shopping_list")
    if not isinstance(entries, list):
        raise BarcodeError("No se pudo consultar la lista de compra")
    quantities = {}
    for item in entries:
        if int(item.get("shopping_list_id") or 1) != 1 or item.get("done"):
            continue
        pid = int(item.get("product_id") or 0)
        qty = Decimal(str(item.get("amount") if item.get("amount") is not None else 1))
        if not qty.is_finite() or qty < 0:
            raise BarcodeError("Cantidad inválida en la lista de compra")
        quantities[pid] = quantities.get(pid, Decimal("0")) + qty
    for row in rows:
        unit = row["unit"].casefold().strip()
        is_kg = unit in ("kg", "kilogram", "kilograms", "kilogramo", "kilogramos")
        qty = quantities.get(row["id"], Decimal("0"))
        row["shopping_amount"] = format(qty.quantize(Decimal("0.01")), "f").rstrip("0").rstrip(".") if qty else "0"
        row["shopping_step"] = "0.10" if is_kg else "1"
        row["shopping_unit"] = "kg" if is_kg else row["unit"]
        row["shopping_can_subtract"] = qty > 0
    return rows


def change_shopping_quantity(product_id, direction):
    """One-tap increase/decrease in Grocy stock units; never modify pantry stock."""
    try:
        pid = int(product_id)
    except (ValueError, TypeError) as exc:
        raise BarcodeError("Producto no válido") from exc
    if pid <= 0 or direction not in ("plus", "minus"):
        raise BarcodeError("Operación de lista de compra no válida")
    products = grocy("GET", "objects/products")
    units = grocy("GET", "objects/quantity_units")
    entries = grocy("GET", "objects/shopping_list")
    if not all(isinstance(x, list) for x in (products, units, entries)):
        raise BarcodeError("No se pudo consultar Grocy")
    product = next((p for p in products if int(p["id"]) == pid), None)
    if product is None:
        raise BarcodeError("El producto ya no existe")
    unit_id = int(product["qu_id_stock"])
    unit = next((str(u["name"]) for u in units if int(u["id"]) == unit_id), "")
    kg = unit.casefold().strip() in ("kg", "kilogram", "kilograms", "kilogramo", "kilogramos")
    step = Decimal("0.10") if kg else Decimal("1")
    current = Decimal("0")
    for entry in entries:
        if (int(entry.get("shopping_list_id") or 1) == 1
                and int(entry.get("product_id") or 0) == pid and not entry.get("done")):
            amount = Decimal(str(entry.get("amount") if entry.get("amount") is not None else 1))
            if not amount.is_finite() or amount < 0:
                raise BarcodeError("Cantidad inválida en la lista")
            current += amount
    if direction == "minus" and current == 0:
        return {"name": str(product["name"]), "amount": "0"}
    amount = step if direction == "plus" else min(step, current)
    path = "stock/shoppinglist/add-product" if direction == "plus" else "stock/shoppinglist/remove-product"
    body = {"product_id": pid, "list_id": 1, "product_amount": float(amount)}
    if direction == "plus":
        body["qu_id"] = unit_id
    grocy("POST", path, body)
    updated = current + amount if direction == "plus" else current - amount
    return {"name": str(product["name"]), "amount": format(updated, "f")}


def shopping_list_snapshot():
    """Read Grocy's default shopping list and resolve catalog names."""
    entries = grocy("GET", "objects/shopping_list")
    products = grocy("GET", "objects/products")
    units = grocy("GET", "objects/quantity_units")
    if not all(isinstance(x, list) for x in (entries, products, units)):
        raise BarcodeError("Grocy devolvió una lista de compra no válida")
    by_product = {int(p["id"]): p for p in products}
    by_unit = {int(u["id"]): str(u["name"]) for u in units}
    rows = []
    for entry in entries:
        if int(entry.get("shopping_list_id") or 1) != 1:
            continue
        pid = int(entry.get("product_id") or 0)
        product = by_product.get(pid)
        name = str(product["name"]) if product else str(entry.get("note") or "Artículo sin nombre")
        amount = Decimal(str(entry.get("amount") or 1))
        if not amount.is_finite() or amount < 0:
            raise BarcodeError("Cantidad no válida en la lista de compra")
        unit_id = int(entry.get("qu_id") or (product or {}).get("qu_id_stock") or 0)
        rows.append({
            "image_url": saved_photo(product) if product else None,
            "id": int(entry["id"]),
            "product_id": pid,
            "name": name,
            "amount": format(amount.normalize(), "f"),
            "unit": by_unit.get(unit_id, "ud."),
            "done": bool(entry.get("done")),
        })
    return sorted(rows, key=lambda r: (r["done"], r["name"].casefold(), r["id"]))


def shopping_product_options(product_id):
    """Offer stock unit and purchasing unit only when Grocy defines a safe factor."""
    try:
        pid = int(product_id)
    except (TypeError, ValueError) as exc:
        raise BarcodeError("Producto no válido") from exc
    if pid <= 0:
        raise BarcodeError("Producto no válido")
    product = grocy("GET", f"objects/products/{pid}")
    if not isinstance(product, dict) or int(product.get("id") or 0) != pid:
        raise BarcodeError("Producto inexistente")
    units = {int(u["id"]): str(u["name"]) for u in grocy("GET", "objects/quantity_units")}
    stock_id = int(product["qu_id_stock"])
    available = [{"id": stock_id, "name": units.get(stock_id, "Unidad de stock"), "factor": "1"}]
    purchase_id = int(product.get("qu_id_purchase") or stock_id)
    factor = Decimal(str(product.get("qu_factor_purchase_to_stock") or 0))
    if purchase_id != stock_id and factor.is_finite() and factor > 0:
        available.append({"id": purchase_id, "name": units.get(purchase_id, "Unidad de compra"),
                          "factor": str(factor)})
    return {"id": pid, "name": str(product["name"]), "units": available}


def add_to_shopping_list(product_id, amount="1", unit_id=None):
    """Add a chosen quantity to Grocy, converting purchasing units into stock units."""
    product = shopping_product_options(product_id)
    try:
        qty = Decimal(str(amount).strip().replace(",", "."))
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise BarcodeError("Cantidad de compra no válida") from exc
    if not qty.is_finite() or qty <= 0 or qty.as_tuple().exponent < -2:
        raise BarcodeError("Introduce una cantidad positiva con máximo dos decimales")
    if unit_id in (None, ""):
        unit_id = product["units"][0]["id"]
    try:
        chosen = next(u for u in product["units"] if u["id"] == int(unit_id))
    except (ValueError, TypeError, StopIteration) as exc:
        raise BarcodeError("Unidad de compra no compatible con el producto") from exc
    stock_amount = qty * Decimal(chosen["factor"])
    if not stock_amount.is_finite() or stock_amount <= 0:
        raise BarcodeError("La conversión de cantidad no es válida")
    grocy("POST", "stock/shoppinglist/add-product", {
        "product_id": product["id"], "qu_id": chosen["id"],
        "list_id": 1, "product_amount": float(stock_amount),
    })
    return product["name"]



def update_shopping_list_item(item_id, done):
    """Mark an existing list entry done/undone, without moving stock."""
    item_id = int(item_id)
    if item_id <= 0:
        raise BarcodeError("Artículo de compra no válido")
    item = grocy("GET", f"objects/shopping_list/{item_id}")
    if not isinstance(item, dict) or int(item.get("shopping_list_id") or 1) != 1:
        raise BarcodeError("Artículo de compra no disponible")
    grocy("PUT", f"objects/shopping_list/{item_id}", {"done": 1 if done else 0})


def remove_shopping_list_item(item_id):
    """Remove only a default-list entry, without changing inventory."""
    item_id = int(item_id)
    if item_id <= 0:
        raise BarcodeError("Artículo de compra no válido")
    item = grocy("GET", f"objects/shopping_list/{item_id}")
    if not isinstance(item, dict) or int(item.get("shopping_list_id") or 1) != 1:
        raise BarcodeError("Artículo de compra no disponible")
    grocy("DELETE", f"objects/shopping_list/{item_id}")


PACK_MARKER = re.compile(r"(?:\n|^)\[Despensa: unidades_por_envase=(\d+)\]\s*")

def product_detail(product_id):
    """Get one product's editable metadata and known barcodes."""
    pid = int(product_id)
    if pid <= 0:
        raise BarcodeError("Producto no válido")
    product = grocy("GET", f"objects/products/{pid}")
    if not isinstance(product, dict) or int(product.get("id", 0)) != pid:
        raise BarcodeError("Producto inexistente")
    description = str(product.get("description") or "")
    marker = PACK_MARKER.search(description)
    codes = [str(item["barcode"]) for item in grocy("GET", "objects/product_barcodes")
             if int(item["product_id"]) == pid]
    return {
        "id": pid, "name": str(product["name"]),
        "pack_size": int(marker.group(1)) if marker else 1,
        "description": PHOTO_MARKER.sub("", PACK_MARKER.sub("", description)).strip(),
        "image_url": saved_photo(product),
        "barcodes": codes,
        "unit_id": int(product["qu_id_stock"]),
        "units": sorted(
            [{"id": int(unit["id"]), "name": str(unit["name"])}
             for unit in grocy("GET", "objects/quantity_units")],
            key=lambda unit: unit["name"].casefold()),
        "stock_amount": str(grocy("GET", f"stock/products/{pid}").get("stock_amount", 0)),
    }


def update_product_info(product_id, name, pack_size, unit_id=None):
    """Edit name and package metadata only. No stock units are changed."""
    pid = int(product_id)
    if pid <= 0:
        raise BarcodeError("Producto no válido")
    name = (name or "").strip()
    if not name or len(name) > 200:
        raise BarcodeError("Indica un nombre de 1 a 200 caracteres")
    try:
        pack_size = int(pack_size)
    except (TypeError, ValueError) as exc:
        raise BarcodeError("Unidades por envase no válidas") from exc
    if not 1 <= pack_size <= 1000:
        raise BarcodeError("Las unidades por envase deben estar entre 1 y 1000")
    product = grocy("GET", f"objects/products/{pid}")
    if not isinstance(product, dict) or int(product.get("id", 0)) != pid:
        raise BarcodeError("Producto inexistente")
    current_unit = int(product["qu_id_stock"])
    if unit_id in (None, ""):
        unit_id = current_unit
    try:
        unit_id = int(unit_id)
    except (TypeError, ValueError) as exc:
        raise BarcodeError("Unidad de medida no válida") from exc
    if unit_id != current_unit:
        known_units = {int(unit["id"]) for unit in grocy("GET", "objects/quantity_units")}
        if unit_id not in known_units:
            raise BarcodeError("La unidad seleccionada no existe en Grocy")
        current_stock = Decimal(str(
            grocy("GET", f"stock/products/{pid}").get("stock_amount", 0)))
        if not current_stock.is_finite() or current_stock != 0:
            raise BarcodeError(
                "No se puede cambiar la unidad con existencias. "
                "Primero hay que convertir o ajustar el stock en Grocy, "
                "para no interpretar unidades como kilogramos.")
    description = PACK_MARKER.sub("", str(product.get("description") or "")).strip()
    if pack_size != 1:
        description = (description + "\n" if description else "") + (
            f"[Despensa: unidades_por_envase={pack_size}]")
    changes = {"name": name, "description": description}
    if unit_id != current_unit:
        changes["qu_id_stock"] = unit_id
    grocy("PUT", f"objects/products/{pid}", changes)
    return {"id": pid, "name": name, "pack_size": pack_size, "unit_id": unit_id}


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

def associate_product_barcode(product_id, barcode):
    """Attach barcode to an explicitly identified product; no stock movement."""
    barcode = validate_barcode(barcode)
    pid = int(product_id)
    if pid <= 0:
        raise BarcodeError("Producto no válido")
    product = grocy("GET", f"objects/products/{pid}")
    if not isinstance(product, dict) or int(product.get("id", 0)) != pid:
        raise BarcodeError("Producto inexistente")
    matches = [row for row in grocy("GET", "objects/product_barcodes")
               if str(row["barcode"]) == barcode]
    if matches:
        ids = {int(row["product_id"]) for row in matches}
        if ids == {pid}:
            return {"name": str(product["name"]), "already_linked": True}
        raise BarcodeError("Este código ya pertenece a otro producto. No se ha modificado nada")
    grocy("POST", "objects/product_barcodes", {"product_id": pid, "barcode": barcode})
    return {"name": str(product["name"]), "already_linked": False}


def prepare_stock_adjustment(product_id, desired_amount, expected_amount):
    """Validate a deliberate stock correction without writing to Grocy."""
    pid = int(product_id)
    if pid <= 0:
        raise BarcodeError("Producto no válido")
    try:
        target = Decimal(str(desired_amount).strip().replace(",", "."))
        expected = Decimal(str(expected_amount).strip().replace(",", "."))
    except Exception as exc:
        raise BarcodeError("Introduce una cantidad válida") from exc
    if not target.is_finite() or not expected.is_finite() or target < 0 or expected < 0:
        raise BarcodeError("La cantidad debe ser un número positivo o cero")
    if target.as_tuple().exponent < -2:
        raise BarcodeError("Máximo dos decimales")
    details = grocy("GET", f"stock/products/{pid}")
    current = Decimal(str(details.get("stock_amount", 0)))
    if not current.is_finite() or current != expected:
        raise BarcodeError("El stock ha cambiado desde que abriste la ficha. Actualízala y vuelve a intentar.")
    if current == target:
        raise BarcodeError("La cantidad indicada ya es la actual")
    return {"product_id": pid, "before": str(current), "after": str(target),
            "difference": str(abs(target - current)), "direction": "add" if target > current else "consume"}


def apply_stock_adjustment(preview):
    """Apply an explicitly confirmed difference, after checking for stale stock."""
    pid = int(preview["product_id"])
    validated = prepare_stock_adjustment(pid, preview["after"], preview["before"])
    if validated["direction"] != preview["direction"] or validated["difference"] != preview["difference"]:
        raise BarcodeError("El ajuste ha cambiado; debes revisarlo de nuevo")
    diff = validated["difference"]
    if validated["direction"] == "add":
        location = int(__import__("os").environ.get("GROCY_LOCATION_ID", "2"))
        grocy("POST", f"stock/products/{pid}/add", {
            "amount": float(Decimal(diff)), "price": 0,
            "best_before_date": "2999-12-31",
            "location_id": location, "note": "Corrección manual desde Despensa"})
    else:
        grocy("POST", f"stock/products/{pid}/consume", {
            "amount": float(Decimal(diff)), "spoiled": False})
    return validated


def _get_name_and_id(barcode):
    product = find_product(barcode)
    if product is None:
        raise BarcodeError("No existe un producto con este código")
    return product["name"], int(product["id"])

def new_product_units():
    """Offer real Grocy stock units when creating a catalog product."""
    units = grocy("GET", "objects/quantity_units")
    if not isinstance(units, list):
        raise BarcodeError("No se han podido cargar las unidades de Grocy")
    return sorted(
        [{"id": int(u["id"]), "name": str(u["name"])} for u in units],
        key=lambda u: u["name"].casefold())


def _new_product_match(name, barcode, products, barcodes):
    """Find an existing product by exact normalized name or scanned barcode."""
    folded = " ".join(name.casefold().split())
    by_id = {int(p["id"]): p for p in products}
    if barcode:
        for row in barcodes:
            if str(row.get("barcode")) == barcode:
                pid = int(row["product_id"])
                if pid in by_id:
                    return {"id": pid, "name": str(by_id[pid]["name"])}
                raise BarcodeError("El código ya está asociado en Grocy, pero no se encuentra su producto")
    for product in products:
        if " ".join(str(product["name"]).casefold().split()) == folded:
            return {"id": int(product["id"]), "name": str(product["name"])}
    return None


def create_catalog_product(name, barcode="", unit_id=None, initial_stock="0", location_id=2, image_url=None):
    """Create only new products; an existing match is returned without any writes."""
    name = (name or "").strip()
    if not name or len(name) > 200:
        raise BarcodeError("Introduce un nombre de producto de 1 a 200 caracteres")
    barcode = (barcode or "").strip()
    if barcode:
        barcode = validate_barcode(barcode)
    try:
        unit_id = int(unit_id)
        location_id = int(location_id)
        amount = Decimal(str(initial_stock).strip().replace(",", "."))
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise BarcodeError("Unidad o cantidad inicial no válida") from exc
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise BarcodeError("La cantidad inicial debe ser positiva o cero, con máximo dos decimales")
    units = new_product_units()
    if unit_id not in {u["id"] for u in units}:
        raise BarcodeError("Selecciona una unidad de medida válida de Grocy")
    products = grocy("GET", "objects/products")
    barcodes = grocy("GET", "objects/product_barcodes")
    if not isinstance(products, list) or not isinstance(barcodes, list):
        raise BarcodeError("No se ha podido verificar el catálogo de Grocy")
    existing = _new_product_match(name, barcode, products, barcodes)
    if existing:
        return {"created": False, "product_id": existing["id"], "name": existing["name"]}
    from product_images import safe_image_url
    safe_url = safe_image_url(image_url)
    result = grocy("POST", "objects/products", {
        "name": name, "location_id": location_id, "qu_id_stock": unit_id,
        "qu_id_purchase": unit_id, "min_stock_amount": 0,
        "description": "[Despensa: imagen=" + safe_url + "]" if safe_url else "",
    })
    pid = int(result["created_object_id"])
    if barcode:
        grocy("POST", "objects/product_barcodes", {"product_id": pid, "barcode": barcode})
    if amount > 0:
        grocy("POST", f"stock/products/{pid}/add", {
            "amount": float(amount), "price": 0, "best_before_date": "2999-12-31",
            "location_id": location_id, "note": "Stock inicial al crear el producto desde Despensa",
        })
    return {"created": True, "product_id": pid, "name": name}


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

def consume_quantity(barcode, amount, add_to_list=False):
    """Consume a chosen stock amount; optionally replenish Grocy's shopping list."""
    name, pid = _get_name_and_id(barcode)
    try:
        quantity = Decimal(str(amount).strip().replace(",", "."))
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise BarcodeError("Cantidad a consumir no válida") from exc
    if not quantity.is_finite() or quantity <= 0 or quantity.as_tuple().exponent < -2:
        raise BarcodeError("Introduce una cantidad mayor que cero, con máximo dos decimales")
    details = grocy("GET", f"stock/products/{pid}")
    available = Decimal(str(details.get("stock_amount", 0)))
    if not available.is_finite() or available < quantity:
        raise BarcodeError("No hay suficiente stock para consumir esa cantidad")
    grocy("POST", f"stock/products/{pid}/consume",
          {"amount": float(quantity), "spoiled": False})
    shopping_added = False
    shopping_error = False
    if add_to_list:
        try:
            product = grocy("GET", f"objects/products/{pid}")
            grocy("POST", "stock/shoppinglist/add-product", {
                "product_id": pid, "list_id": 1, "product_amount": float(quantity),
                "qu_id": int(product["qu_id_stock"]),
            })
            shopping_added = True
        except Exception:
            # Stock was already consumed. Report the partial result, never invite
            # a blind retry that could consume the same amount a second time.
            shopping_error = True
    return {"product_id": pid, "name": name, "amount": str(quantity),
            "shopping_added": shopping_added, "shopping_error": shopping_error}


def remove_one(barcode):
    """Consume exactly one stock unit, preserving the product in the catalog."""
    name, pid = _get_name_and_id(barcode)
    details = grocy("GET", f"stock/products/{pid}")
    amount = Decimal(str(details.get("stock_amount", 0)))
    if amount < 1:
        raise BarcodeError("El producto no tiene una unidad completa disponible en stock")
    grocy("POST", f"stock/products/{pid}/consume", {"amount": 1, "spoiled": False})
    return {"product_id": pid, "name": name}
