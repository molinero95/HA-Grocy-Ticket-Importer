"""Look up exact barcodes in Open Food Facts and Open Products Facts."""
import json
import urllib.request
from urllib.parse import urlparse
from barcode_stock import validate_barcode

SOURCES = (
    ("Open Food Facts", "https://world.openfoodfacts.org/api/v2/product/", "https://world.openfoodfacts.org/product/"),
    ("Open Products Facts", "https://world.openproductsfacts.org/api/v2/product/", "https://world.openproductsfacts.org/product/"),
)
IMAGE_HOSTS = {"images.openfoodfacts.org", "images.openproductsfacts.org"}


def safe_image_url(url):
    if not isinstance(url, str):
        return None
    parts = urlparse(url)
    if parts.scheme != "https" or parts.hostname not in IMAGE_HOSTS or parts.username or parts.password or parts.port not in (None, 443):
        return None
    return url


def lookup_image(barcode):
    barcode = validate_barcode(barcode)
    errors = []
    for source, api, website in SOURCES:
        req = urllib.request.Request(
            api + barcode + "?fields=code,product_name,image_front_url,image_front_small_url",
            headers={"User-Agent": "HAGrocyTicketImporter/0.13 (https://github.com/molinero95/HA-Grocy-Ticket-Importer)", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.load(response)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        product = data.get("product") or {}
        if data.get("status") != 1 or str(product.get("code")) != barcode:
            continue
        image = safe_image_url(product.get("image_front_small_url")) or safe_image_url(product.get("image_front_url"))
        name = str(product.get("product_name") or "").strip()[:200]
        if image or name:
            return {"barcode": barcode, "name": name, "image_url": image,
                    "source_url": website + barcode, "attribution": "Datos: " + source}
    if len(errors) == len(SOURCES):
        raise ConnectionError("No se pudo consultar ninguna fuente de productos")
    return None
