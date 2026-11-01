"""Advisory duplicate pairs, excluding explicit, reversible differences."""
import difflib
import unicodedata
import barcode_stock
from duplicate_review import differences


def detect_duplicates():
    products = barcode_stock.grocy('GET', 'objects/products')
    codes = barcode_stock.grocy('GET', 'objects/product_barcodes')
    if not isinstance(products, list) or not isinstance(codes, list):
        raise ValueError('Unexpected Grocy catalog response')
    ignored = {(row['left_id'], row['right_id']) for row in differences()}
    entries = {int(p['id']): {'id': int(p['id']), 'name': str(p['name']), 'barcodes': []}
               for p in products if barcode_stock._done(p.get('active', True))}
    for code in codes:
        item = entries.get(int(code['product_id']))
        if item and code.get('barcode'): item['barcodes'].append(str(code['barcode']))
    def normalized(name):
        return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', name.casefold()) if not unicodedata.combining(c)).split())
    results = []
    items = sorted(entries.values(), key=lambda p: p['id'])
    for i, left in enumerate(items):
        a = normalized(left['name'])
        for right in items[i+1:]:
            if (left['id'], right['id']) in ignored: continue
            b = normalized(right['name'])
            reason = None
            if set(left['barcodes']) & set(right['barcodes']): reason = 'Mismo código de barras'
            elif a and a == b: reason = 'Nombre idéntico'
            elif len(a) >= 6 and len(b) >= 6 and difflib.SequenceMatcher(None, a, b).ratio() >= .88:
                reason = 'Nombres parecidos · revisar'
            if reason: results.append({'reason': reason, 'items': [left, right]})
    return results
