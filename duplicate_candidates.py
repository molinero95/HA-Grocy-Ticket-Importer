"""Advisory duplicate pairs, excluding explicit, reversible differences."""
import difflib
import unicodedata
import barcode_stock
from duplicate_review import differences


def normalized(name):
    import re
    text = ''.join(c for c in unicodedata.normalize('NFKD', name.casefold()) if not unicodedata.combining(c))
    # Equivalent printed sizes should not hide a duplicate (1 kg / 1000 g).
    from decimal import Decimal
    def size(match):
        amount = Decimal(match[1].replace(',', '.'))
        factor = 1000 if match[2] in ('kg', 'l', 'litro', 'litros') else 1
        family = 'g' if match[2] in ('kg', 'g', 'gr', 'gramos') else 'ml'
        return ' ' + format((amount * factor).normalize(), 'f') + family + ' '
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*(kg|gramos|gr|g|litros|litro|ml|l)\b', size, text)
    tokens = re.findall(r'[a-z0-9]+', text)
    return ' '.join(token for token in tokens if token not in {'de', 'del', 'el', 'la', 'los', 'las', 'y'})


def similar_names(a, b):
    import re
    if not a or not b: return False
    # Compare meaningful words independently of word order and punctuation/size.
    words = lambda value: [word for word in value.split() if not re.fullmatch(r'\d+(?:g|ml)?', word)]
    left, right = words(a), words(b)
    if not left or not right: return False
    ordered = difflib.SequenceMatcher(None, ' '.join(sorted(left)), ' '.join(sorted(right))).ratio()
    if min(len(''.join(left)), len(''.join(right))) >= 5 and ordered >= .82:
        return True
    small, large = sorted((set(left), set(right)), key=len)
    common = small & large
    if len(common) >= 2 and len(common) / len(small) >= .67:
        return True
    if len(small) == 1 and small <= large and len(next(iter(small))) >= 5:
        return True
    return False


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
            elif similar_names(a, b):
                reason = 'Nombres o variantes parecidos · revisar marca y formato'
            if reason: results.append({'reason': reason, 'items': [left, right]})
    return results
