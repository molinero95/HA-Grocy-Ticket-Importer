"""Look up exact barcodes in the food, product and cosmetics open catalogs."""
import json
import urllib.request
from urllib.error import HTTPError
from urllib.parse import urlparse
from barcode_stock import validate_barcode

SOURCES = (
    ("Open Food Facts", "https://world.openfoodfacts.org/api/v2/product/", "https://world.openfoodfacts.org/product/"),
    ("Open Products Facts", "https://world.openproductsfacts.org/api/v2/product/", "https://world.openproductsfacts.org/product/"),
    ("Open Beauty Facts", "https://world.openbeautyfacts.org/api/v2/product/", "https://world.openbeautyfacts.org/product/"),
)
IMAGE_HOSTS = {"images.openfoodfacts.org", "images.openproductsfacts.org", "images.openbeautyfacts.org"}


def safe_image_url(url):
    if not isinstance(url, str):
        return None
    try:
        parts = urlparse(url)
        valid = parts.scheme == "https" and parts.hostname in IMAGE_HOSTS and not parts.username and not parts.password and parts.port in (None, 443)
    except ValueError:
        return None
    if not valid:
        return None
    return url


def lookup_image(barcode):
    barcode = validate_barcode(barcode)
    errors = []
    fallback = None
    for source, api, website in SOURCES:
        req = urllib.request.Request(
            api + barcode + "?fields=code,product_name,product_name_es,image_front_url,image_front_small_url",
            headers={"User-Agent": "Despensa/1.2.0 (https://github.com/molinero95/HA-Grocy-Ticket-Importer)", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.load(response)
        except HTTPError as exc:
            # A missing product is a normal catalog miss, not a service outage.
            if exc.code != 404:
                errors.append(type(exc).__name__)
            continue
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        product = data.get("product") if isinstance(data, dict) else None
        if not isinstance(product, dict) or data.get("status") != 1 or str(product.get("code")) != barcode:
            continue
        image = safe_image_url(product.get("image_front_small_url")) or safe_image_url(product.get("image_front_url"))
        name = next((value.strip()[:200] for value in (product.get("product_name_es"), product.get("product_name"))
                     if isinstance(value, str) and value.strip()), "")
        if image or name:
            found = {"barcode": barcode, "name": name, "image_url": image,
                     "source_url": website + barcode, "attribution": "Datos: " + source}
            if image:
                return found
            if fallback is None:
                fallback = found
    if fallback:
        return fallback
    if len(errors) == len(SOURCES):
        raise ConnectionError("No se pudo consultar ninguna fuente de productos")
    return None
