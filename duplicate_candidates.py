"""Read-only duplicate candidates; never merge products automatically."""
import difflib
import unicodedata
import barcode_stock


def detect_duplicates():
    """Read-only candidate groups; never merge catalog entries automatically."""
    products = barcode_stock.grocy("GET", "objects/products")
    codes = barcode_stock.grocy("GET", "objects/product_barcodes")
    if not isinstance(products, list) or not isinstance(codes, list):
        raise ValueError("Unexpected Grocy catalog response")
    by_id = {int(p["id"]): {"id": int(p["id"]), "name": str(p.get("name") or ""), "barcodes": []} for p in products}
    for code in codes:
        item = by_id.get(int(code["product_id"]))
        if item and code.get("barcode"):
            item["barcodes"].append(str(code["barcode"]))
    def normalized(name):
        return " ".join("".join(c for c in unicodedata.normalize("NFKD", name.casefold()) if not unicodedata.combining(c)).split())
    groups = {}
    for item in by_id.values():
        name = normalized(item["name"])
        if name:
            groups.setdefault(("Nombre idéntico", name), {})[item["id"]] = item
        for code in item["barcodes"]:
            groups.setdefault(("Mismo código de barras", code), {})[item["id"]] = item
    results = [{"reason": reason, "items": list(items.values())} for (reason, _), items in groups.items() if len(items) > 1]
    seen = {tuple(sorted(item["id"] for item in group["items"])) for group in results}
    entries = list(by_id.values())
    for i, left in enumerate(entries):
        a = normalized(left["name"])
        if len(a) < 6:
            continue
        for right in entries[i+1:]:
            b = normalized(right["name"])
            pair = tuple(sorted((left["id"], right["id"])))
            if pair not in seen and len(b) >= 6 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.88:
                results.append({"reason": "Nombres parecidos · revisar", "items": [left, right]})
                seen.add(pair)
    return results

