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


def safe_commons_image_url(url):
    """Only raster files served from Commons, never arbitrary thumbnail URLs."""
    import re
    if not _trusted_url(url, {'upload.wikimedia.org', 'thumb.wikimedia.org'}):
        return None
    parts = urlparse(url)
    from urllib.parse import parse_qs, urlunparse
    if (not parts.path.startswith('/wikipedia/commons/') or parts.fragment
            or set(parse_qs(parts.query, keep_blank_values=True)) - {'utm_source', 'utm_campaign', 'utm_content'}
            or re.search(r'[\s\[\]<>]', url)
            or not parts.path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))):
        return None
    # Commons currently adds attribution tracking parameters to imageinfo URLs.
    return urlunparse(parts._replace(query=''))


def safe_saved_image_url(url):
    return safe_image_url(url) or safe_commons_image_url(url)


class _NoCommonsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise URLError('Redirección de imágenes no permitida')


def _commons_query(**parameters):
    from urllib.parse import urlencode
    url = 'https://commons.wikimedia.org/w/api.php?' + urlencode({
        'action': 'query', 'format': 'json', 'formatversion': 2,
        'prop': 'imageinfo', 'iiprop': 'url|mime|mediatype|extmetadata',
        'iiurlwidth': 480,
        'iiextmetadatafilter': 'LicenseShortName|Artist|Restrictions', **parameters,
    })
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Despensa/1.26.0 (https://github.com/molinero95/HA-Grocy-Ticket-Importer)',
        'Accept': 'application/json',
    })
    # Fixed API, bounded response and no redirects, retries or image downloads.
    with urllib.request.build_opener(_NoCommonsRedirect()).open(req, timeout=12) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError('Respuesta de imágenes demasiado grande')
    data = json.loads(raw)
    if not isinstance(data, dict) or 'error' in data:
        raise ValueError('Respuesta de imágenes inválida')
    pages = data.get('query', {}).get('pages', [])
    if not isinstance(pages, list):
        raise ValueError('Respuesta de imágenes inválida')
    return pages


def _commons_candidate(page):
    if (not isinstance(page, dict) or page.get('ns') != 6 or page.get('missing')
            or type(page.get('pageid')) is not int or page['pageid'] <= 0
            or not isinstance(page.get('title'), str) or not page['title'].startswith('File:')):
        return None
    infos = page.get('imageinfo')
    if not isinstance(infos, list) or not infos or not isinstance(infos[0], dict):
        return None
    info = infos[0]
    metadata = info.get('extmetadata')
    if not isinstance(metadata, dict):
        return None
    license_info, restrictions = metadata.get('LicenseShortName'), metadata.get('Restrictions', {})
    licenses = {'Public domain': 'https://commons.wikimedia.org/wiki/Help:Public_domain',
                'CC0': 'https://creativecommons.org/publicdomain/zero/1.0/'}
    for version in ('1.0', '2.0', '2.5', '3.0', '4.0'):
        licenses['CC BY ' + version] = 'https://creativecommons.org/licenses/by/' + version + '/'
        licenses['CC BY-SA ' + version] = 'https://creativecommons.org/licenses/by-sa/' + version + '/'
    if (not isinstance(license_info, dict) or license_info.get('value') not in licenses
            or not isinstance(restrictions, dict) or restrictions.get('value')):
        return None
    image = safe_commons_image_url(info.get('thumburl'))
    if (not image or info.get('mime') not in ('image/jpeg', 'image/png', 'image/webp')
            or info.get('mediatype') != 'BITMAP'):
        return None
    source = 'https://commons.wikimedia.org/?curid=' + str(page['pageid'])
    from html.parser import HTMLParser
    class PlainText(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)
    artist = metadata.get('Artist', {})
    text = PlainText()
    text.feed(str(artist.get('value', ''))[:8192] if isinstance(artist, dict) else '')
    author = ' '.join(' '.join(text.parts).split())[:500]
    if license_info['value'].startswith('CC BY') and not author:
        return None
    credit = {'artist': author, 'license': license_info['value'],
              'license_url': licenses[license_info['value']], 'source_url': source, 'image_url': image}
    return {'kind': 'generic', 'file_id': page['pageid'], 'name': page['title'][5:205],
            'barcode': '', 'image_url': image, 'source_url': source, 'search_source_url': source,
            'credit': credit, 'attribution': 'Wikimedia Commons · ' + license_info['value'] + (' · ' + author if author else '')}


def search_generic_photos(name):
    """Explicit, unpaid generic-photo search; no inferred barcode or identity."""
    import re
    if not isinstance(name, str) or not 3 <= len(name.strip()) <= 200:
        raise ValueError('Escribe un nombre de entre 3 y 200 caracteres')
    words = re.findall(r'[^\W_]+', name, flags=re.UNICODE)
    if not words:
        raise ValueError('Escribe el nombre del alimento o producto')
    pages = _commons_query(generator='search', gsrsearch='"' + ' '.join(words) + '" filetype:bitmap',
                           gsrnamespace=6, gsrlimit=12)
    candidates = []
    for page in sorted(pages, key=lambda p: p.get('index', 999) if isinstance(p, dict) else 999):
        found = _commons_candidate(page)
        if found and found['file_id'] not in {c['file_id'] for c in candidates}:
            candidates.append(found)
    return {'candidates': candidates[:6], 'advisory': True}


def verify_generic_photo(file_id):
    if type(file_id) is not int or file_id <= 0:
        return None
    for page in _commons_query(pageids=file_id):
        if isinstance(page, dict) and page.get('pageid') == file_id:
            return _commons_candidate(page)
    return None


class _CatalogRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The universal API redirects between catalogs. Validate before following.
        if not _trusted_url(newurl, CATALOGS):
            raise URLError("Destino de catálogo no permitido")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_catalog(url, barcode):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Despensa/1.7.0 (https://github.com/molinero95/HA-Grocy-Ticket-Importer)", "Accept": "application/json"},
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


def catalog_reference(url):
    """Extract an exact public catalog product ID; never fetch a model-provided URL."""
    import re

    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parts = urlparse(url)
        if (parts.scheme != "https" or parts.username or parts.password
                or parts.port not in (None, 443)):
            return None
        source = next((entry for entry in SOURCES
                       if parts.hostname == urlparse(entry[1]).hostname.removeprefix("world.")
                       or (parts.hostname or "").endswith("." + urlparse(entry[1]).hostname.removeprefix("world."))), None)
        match = re.match(r"^/(?:product|producto|produit|produkt)/([0-9]{8,14})(?:/[^?#]*)?$", parts.path)
        if not source or not match:
            return None
        code = match.group(1)
        # AI discovery only accepts standard GTINs with a valid check digit.
        if len(code) not in (8, 12, 13, 14) or sum(
            int(digit) * (3 if index % 2 == 0 else 1)
            for index, digit in enumerate(reversed(code[:-1]))
        ) % 10 != (-int(code[-1])) % 10:
            return None
        return source, code
    except ValueError:
        return None


def verify_discovered_product(url):
    reference = catalog_reference(url)
    if not reference:
        return None
    source, code = reference
    found = _fetch_catalog(source[1] + code + "?fields=" + FIELDS, code)
    if not found or not found["name"]:
        return None
    return {**found, "search_source_url": url}
