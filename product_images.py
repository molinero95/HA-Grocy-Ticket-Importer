"""Product photo lookup by exact EAN/UPC using Open Food Facts.

Read-only: never changes Grocy or uploads pictures.
"""
import json
import urllib.request
from urllib.parse import urlparse

from barcode_stock import validate_barcode

API = "https://world.openfoodfacts.org/api/v2/product/"
HOST = "images.openfoodfacts.org"

def safe_image_url(url):
    if not isinstance(url, str):
        return None
    parts = urlparse(url)
    if parts.scheme != "https" or parts.hostname != HOST or parts.username or parts.password:
        return None
    return url

def lookup_image(barcode):
    barcode = validate_barcode(barcode)
    req = urllib.request.Request(
        API + barcode + "?fields=code,product_name,image_front_url,image_front_small_url",
        headers={"User-Agent": "HAGrocyTicketImporter/0.1 (https://github.com/molinero95/HA-Grocy-Ticket-Importer)",
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        data = json.load(response)
    product = data.get("product") or {}
    if data.get("status") != 1 or str(product.get("code")) != barcode:
        return None
    image = safe_image_url(product.get("image_front_small_url")) or safe_image_url(product.get("image_front_url"))
    name = str(product.get("product_name") or "").strip()[:200]
    if not image and not name:
        return None
    return {"barcode": barcode, "name": name,
            "image_url": image,
            "source_url": "https://world.openfoodfacts.org/product/" + barcode,
            "attribution": "Imagen: Open Food Facts (CC BY-SA)"}
