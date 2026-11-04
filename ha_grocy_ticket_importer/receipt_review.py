"""Reviewed receipt identities and merchant-scoped mappings in the existing ledger."""
import re
import sqlite3
import unicodedata
from contextlib import closing
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path


def total_warning(receipt):
    """Monetary reconciliation is advisory; never infer a stock adjustment."""
    try:
        cent = Decimal('.01')
        calculated = sum(((Decimal(str(item['quantity'])) * Decimal(str(item['unit_price']))).quantize(cent, rounding=ROUND_HALF_UP)
                          for item in receipt['items']), Decimal('0'))
        printed = Decimal(str(receipt['total'])).quantize(cent, rounding=ROUND_HALF_UP)
        if not calculated.is_finite() or not printed.is_finite():
            raise ValueError('Non-finite total')
        if calculated != printed:
            return f'Los importes no coinciden (calculado {calculated:.2f} €, ticket {printed:.2f} €). La diferencia de precio no bloquea la importación; revisa productos y cantidades.'
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return 'No se pudo comprobar el importe del ticket. El total monetario es informativo; revisa productos y cantidades.'
    return None


def is_shopping_bag(name):
    """Conservative carry-bag names; never match bagged food or bin bags."""
    text = unicodedata.normalize('NFKD', str(name)).casefold()
    text = ''.join(c for c in text if not unicodedata.combining(c))
    words = re.findall(r'[a-z0-9]+', text)
    allowed = {'de', 'la', 'compra', 'plastico', 'papel', 'reciclada', 'reciclado', 'recicladas',
               'reutilizable', 'reutilizables', 'compostable', 'compostables', 'biodegradable',
               'biodegradables', 'camiseta', 'rafia', 'grande', 'mediana', 'pequena', 'con', 'asas',
               'ecologica', 'ecologicas'}
    return bool(words and words[0] in ('bolsa', 'bolsas')
                and all(word in allowed or word.isdigit() for word in words[1:]))


def key(value):
    value = unicodedata.normalize('NFKC', str(value)).casefold()
    return ' '.join(value.split())


def mappings(path, merchant):
    if not Path(path).is_file():
        return {}
    with closing(sqlite3.connect(path)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='receipt_product_mappings'").fetchone():
            return {}
        rows = db.execute('SELECT source_name, product_id, stock_unit, pieces_per_pack FROM receipt_product_mappings WHERE merchant=?', (key(merchant),)).fetchall()
    return {name: {'product_id': pid, 'stock_unit': unit, 'pieces_per_pack': factor} for name, pid, unit, factor in rows}


def remember(db, merchant, item, product_id):
    if item.get('remember_product') is not True or not str(merchant).strip():
        return
    db.execute('''CREATE TABLE IF NOT EXISTS receipt_product_mappings (
        merchant TEXT NOT NULL, source_name TEXT NOT NULL, product_id INTEGER NOT NULL,
        stock_unit TEXT NOT NULL, pieces_per_pack INTEGER NOT NULL,
        PRIMARY KEY(merchant, source_name))''')
    db.execute('INSERT OR REPLACE INTO receipt_product_mappings VALUES (?,?,?,?,?)',
               (key(merchant), key(item.get('original_name', item['name'])), int(product_id), item['stock_unit'], int(item.get('pieces_per_pack', 1))))


def validate_review(item):
    if item.get('product_mode') == 'skip':
        if item.get('product_id') is not None or item.get('remember_product') not in (None, False) or item.get('stock_to_add') is not None or item.get('expected_stock') is not None:
            raise ValueError('Omitted lines cannot select, remember or add a product')
        # Preserve the original line in total validation; stock-only inputs do
        # not prevent deliberately omitting this line from inventory.
        quantity = Decimal(str(item['quantity']))
        if not quantity.is_finite() or quantity <= 0: raise ValueError('Invalid original quantity')
        return quantity, 1
    quantity = Decimal(str(item.get('purchase_units', item['quantity'])))
    factor = Decimal(str(item.get('pieces_per_pack', 1)))
    if not quantity.is_finite() or not 0 < quantity <= 1000000 or quantity != quantity.quantize(Decimal('.001')):
        raise ValueError('Invalid purchase quantity')
    if not factor.is_finite() or factor != factor.to_integral_value() or not 1 <= factor <= 1000:
        raise ValueError('Invalid pack conversion')
    if 'unit_confirmed' in item and type(item['unit_confirmed']) is not bool:
        raise ValueError('Invalid unit confirmation')
    unit = item.get('stock_unit')
    if unit not in (None, 'piece', 'kg'):
        raise ValueError('Invalid stock unit')
    if unit == 'piece' and item.get('stock_to_add') is None and quantity != quantity.to_integral_value():
        raise ValueError('Pieces require whole quantities')
    if unit == 'kg' and factor != 1:
        raise ValueError('Kilograms cannot be converted to pieces')
    mode = item.get('product_mode', 'auto')
    if mode not in ('auto', 'existing', 'new'):
        raise ValueError('Invalid product selection')
    if mode == 'existing' and (type(item.get('product_id')) is not int or item['product_id'] <= 0):
        raise ValueError('Select an existing product')
    if mode != 'existing' and item.get('product_id') is not None:
        raise ValueError('Unexpected product identity')
    if 'remember_product' in item and type(item['remember_product']) is not bool:
        raise ValueError('Invalid mapping preference')
    if item.get('remember_product') and (mode == 'auto' or unit is None):
        raise ValueError('An explicit product and unit are required to remember a mapping')
    if item.get('stock_to_add') is not None:
        if mode != 'existing' or unit not in ('piece', 'kg'):
            raise ValueError('Direct stock requires an explicitly selected existing product')
        added = Decimal(str(item['stock_to_add']))
        expected = Decimal(str(item.get('expected_stock', 'NaN')))
        if not added.is_finite() or not 0 < added <= 1000000 or added != added.quantize(Decimal('.001')):
            raise ValueError('Invalid stock addition')
        if unit == 'piece' and added != added.to_integral_value(): raise ValueError('Pieces require whole additions')
        if not expected.is_finite() or not 0 <= expected <= 1000000000000: raise ValueError('Unknown starting stock')
    return quantity, int(factor)


def has_review(output):
    return bool(re.search(r'^\[\d+\] (?:REVIEW|SKIP pending)\b', output, re.MULTILINE))


def list_aliases(path):
    """Read every remembered receipt identity, including unavailable products."""
    if not Path(path).is_file(): return []
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='receipt_product_mappings'").fetchone(): return []
        rows = db.execute('SELECT merchant, source_name, product_id, stock_unit, pieces_per_pack FROM receipt_product_mappings ORDER BY merchant, source_name').fetchall()
    return [dict(zip(('merchant', 'source_name', 'product_id', 'stock_unit', 'pieces_per_pack'), row)) for row in rows]


def change_alias(path, payload, products, *, delete=False):
    """Expected-row guarded edit/delete of future suggestions; ledger stays intact."""
    original = payload.get('expected')
    fields = ('merchant', 'source_name', 'product_id', 'stock_unit', 'pieces_per_pack')
    if not isinstance(original, dict) or any(field not in original for field in fields):
        raise ValueError('Actualiza los alias antes de editar')
    if any(not isinstance(original[field], str) or not original[field].strip() for field in ('merchant', 'source_name')):
        raise ValueError('Asociación no válida')
    if type(original['product_id']) is not int or type(original['pieces_per_pack']) is not int:
        raise ValueError('Asociación no válida')
    values = tuple(original[field] for field in fields)
    if not delete:
        merchant, source = payload.get('merchant'), payload.get('source_name')
        if any(not isinstance(value, str) or not value.strip() or len(value) > 200 for value in (merchant, source)):
            raise ValueError('Indica supermercado y texto del ticket de hasta 200 caracteres')
        pid = payload.get('product_id')
        product = next((p for p in products if type(pid) is int and p['id'] == pid), None)
        if product is None: raise ValueError('Selecciona un producto disponible y con unidades compatibles')
        replacement = (key(merchant), key(source), pid, product['stock_unit'], product['pieces_per_pack'])
    # No table creation or ledger bootstrap from the management view.
    if not Path(path).is_file(): raise ValueError('La asociación ya no existe. Actualiza los alias')
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='receipt_product_mappings'").fetchone():
            raise ValueError('La asociación ya no existe. Actualiza los alias')
        actual = db.execute('SELECT merchant, source_name, product_id, stock_unit, pieces_per_pack FROM receipt_product_mappings WHERE merchant=? AND source_name=?', values[:2]).fetchone()
        if actual != values: raise ValueError('La asociación ha cambiado. Actualiza los alias antes de guardar')
        if not delete:
            collision = db.execute('SELECT 1 FROM receipt_product_mappings WHERE merchant=? AND source_name=?', replacement[:2]).fetchone()
            if replacement[:2] != values[:2] and collision:
                raise ValueError('Ese texto ya tiene una asociación en ese supermercado. Edita su fila')
        db.execute('DELETE FROM receipt_product_mappings WHERE merchant=? AND source_name=?', values[:2])
        if not delete: db.execute('INSERT INTO receipt_product_mappings VALUES (?,?,?,?,?)', replacement)


def suggestions(name, products):
    """Advisory name ranking only; never bind a product from a fuzzy match."""
    import difflib
    from duplicate_candidates import normalized
    source = normalized(name)
    if len(source) < 3: return []
    ranked = []
    for product in products:
        candidate = normalized(product['name'])
        similarity = difflib.SequenceMatcher(None, source, candidate).ratio()
        left, right = set(source.split()), set(candidate.split())
        shared = {word for word in left & right if len(word) >= 3 and not word.isdigit()}
        if shared: similarity = max(similarity, .65 + .3 * len(shared) / max(len(left), len(right)))
        if similarity >= .55: ranked.append((similarity, product['name'].casefold(), product['id']))
    return [row[2] for row in sorted(ranked, key=lambda row: (-row[0], row[1], row[2]))[:3]]


def review_issues(output):
    """Map importer REVIEW lines to zero-based UI rows, without parsing names."""
    reasons = {
        'Stock changed since receipt review': 'El stock ha cambiado. Pulsa Actualizar stock y catálogo y revisa la cantidad final.',
        'Select the remembered product explicitly before import': 'Elige el producto de la asociación guardada o crea uno nuevo.',
        'Selected product is missing or archived': 'El producto elegido ya no está disponible. Selecciona otro.',
        'Product name already exists; select the existing product': 'Ese nombre ya existe. Selecciona el producto existente.',
        'Matching product is archived': 'La coincidencia no está disponible. Revisa el producto elegido.',
        'Multiple catalog matches': 'Hay varios productos con ese nombre. Elige uno concreto.',
        'Existing product has different stock unit': 'La unidad no coincide con el producto. Vuelve a seleccionarlo.',
        'Saved purchase conversion differs; review product in Grocy': 'La conversión de compra ha cambiado. Actualiza el catálogo y vuelve a elegir el producto.',
        'Fractional quantity without reliable weight unit': 'Confirma si la cantidad corresponde a kilogramos o piezas.',
        'Whole-kg line: could be weighed or packaged': 'Confirma la unidad de stock: peso o producto envasado.',
        'Kilograms cannot be converted to pieces': 'Para kilogramos, la equivalencia del envase debe ser 1.',
        'Create a unique Pack quantity unit in Grocy first': 'Falta una unidad Pack válida para crear este envase.',
    }
    issues = []
    for line in output.splitlines():
        match = re.match(r'^\[(\d+)\] (REVIEW|SKIP pending)\b(.*)$', line)
        if not match: continue
        if match[2] == 'SKIP pending':
            message = 'Esta línea tiene una importación anterior pendiente de comprobar. Revisa Grocy antes de reintentar; omitirla no borra esa protección.'
        else:
            reason = match[3].rsplit(': ', 1)[-1].strip()
            message = reasons.get(reason, 'Esta línea requiere revisión. Consulta su motivo en el resultado de la simulación.')
        issues.append({'index': int(match[1]) - 1, 'message': message})
    return issues
