"""Universal exact-barcode lookup with direct food, product and beauty fallbacks."""
import json
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from barcode_stock import validate_barcode

SOURCES = (
    ("Open Food Facts", "https://world.openfoodfacts.org/api/v2/product/", "https://world.openfoodfacts.org/product/"),
    ("Open Products Facts", "https://world.openproductsfacts.org/api/v2/product/", "https://world.openproductsfacts.org/product/"),
    ("Open Beauty Facts", "https://world.openbeautyfacts.org/api/v2/product/", "https://world.openbeautyfacts.org/product/"),
)
IMAGE_HOSTS = {"images.openfoodfacts.org", "images.openproductsfacts.org", "images.openbeautyfacts.org"}
CATALOGS = {urlparse(api).hostname: (source, website) for source, api, website in SOURCES}
UNIVERSAL_API = "https://world.openfoodfacts.org/api/v3/product/"
FIELDS = "code,product_type,product_name,product_name_es,image_front_url,image_front_small_url"


def _trusted_url(url, hosts):
    if not isinstance(url, str):
        return None
    try:
        parts = urlparse(url)
        valid = parts.scheme == "https" and parts.hostname in hosts and not parts.username and not parts.password and parts.port in (None, 443)
    except ValueError:
        return None
    if not valid:
        return None
    return url


def safe_image_url(url):
    return _trusted_url(url, IMAGE_HOSTS)


class _CatalogRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The universal API redirects between catalogs. Validate before following.
        if not _trusted_url(newurl, CATALOGS):
            raise URLError("Destino de catálogo no permitido")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_catalog(url, barcode):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Despensa/1.6.0 (https://github.com/molinero95/HA-Grocy-Ticket-Importer)", "Accept": "application/json"},
    )
    opener = urllib.request.build_opener(_CatalogRedirectHandler())
    with opener.open(req, timeout=8) as response:
        final_url = response.geturl()
        if not _trusted_url(final_url, CATALOGS):
            raise URLError("Origen de catálogo no permitido")
        data = json.load(response)
    product = data.get("product") if isinstance(data, dict) else None
    if (not isinstance(product, dict) or data.get("status") not in (1, "success", "success_with_errors")
            or str(product.get("code")) != barcode
            or product.get("product_type") not in (None, "food", "beauty", "product")):
        return None
    image = safe_image_url(product.get("image_front_small_url")) or safe_image_url(product.get("image_front_url"))
    name = next((value.strip()[:200] for value in (product.get("product_name_es"), product.get("product_name"))
                 if isinstance(value, str) and value.strip()), "")
    if not image and not name:
        return None
    source, website = CATALOGS[urlparse(final_url).hostname]
    return {"barcode": barcode, "name": name, "image_url": image,
            "source_url": website + barcode, "attribution": "Datos: " + source}


def lookup_image(barcode):
    barcode = validate_barcode(barcode)
    errors = []
    fallback = None
    urls = [UNIVERSAL_API + barcode + "?product_type=all&lc=es&fields=" + FIELDS]
    urls.extend(api + barcode + "?fields=" + FIELDS for _, api, _ in SOURCES)
    for index, url in enumerate(urls):
        try:
            found = _fetch_catalog(url, barcode)
        except HTTPError as exc:
            if exc.code == 404:
                # Universal 404 already means absent from all catalogs.
                if index == 0:
                    return None
            else:
                errors.append(type(exc).__name__)
            continue
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if found:
            if found["image_url"]:
                return found
            if fallback is None:
                fallback = found
    if fallback:
        return fallback
    if len(errors) == len(urls):
        raise ConnectionError("No se pudo consultar ninguna fuente de productos")
    return None
