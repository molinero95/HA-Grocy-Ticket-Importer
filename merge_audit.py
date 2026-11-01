"""Guard Grocy 4.7.1's transactional native merge; never rewrite history ourselves."""
import hashlib
import hmac
import json
from decimal import Decimal
import barcode_stock
from catalog_lifecycle import _local_deletion_blockers, is_active

COLLECTIONS = (
    ('stock', 'Lotes de existencias'), ('stock_log', 'Historial de movimientos'),
    ('product_barcodes', 'Códigos de barras'), ('quantity_unit_conversions', 'Conversiones'),
    ('recipes_pos', 'Ingredientes de recetas'), ('recipes', 'Recetas'),
    ('meal_plan', 'Plan de comidas'), ('shopping_list', 'Listas de compra'),
)


def _rows(collection):
    rows = barcode_stock.grocy('GET', 'objects/' + collection)
    if not isinstance(rows, list) or any(not isinstance(row, dict) or 'id' not in row for row in rows):
        raise ValueError('No se pudieron comprobar las referencias')
    return rows


def _audit(source_id, target_id):
    source_id, target_id = int(source_id), int(target_id)
    if source_id <= 0 or target_id <= 0 or source_id == target_id:
        raise barcode_stock.BarcodeError('Selecciona dos productos distintos')
    source, target = [barcode_stock.grocy('GET', f'objects/products/{pid}') for pid in (source_id, target_id)]
    if any(not isinstance(p, dict) or int(p.get('id', 0)) != pid for p, pid in ((source, source_id), (target, target_id))):
        raise ValueError('Producto no verificado')
    info = barcode_stock.grocy('GET', 'system/info')
    blockers = []
    if info.get('grocy_version', {}).get('Version') != '4.7.1':
        blockers.append('La combinación requiere Grocy 4.7.1, cuyas reglas están verificadas')
    if not all(is_active(p) for p in (source, target)):
        blockers.append('Ambos productos deben estar activos')
    for field in ('qu_id_stock', 'qu_id_purchase', 'qu_id_consume', 'qu_id_price'):
        if str(source.get(field)) != str(target.get(field)):
            blockers.append('Las unidades de stock, compra, consumo o precio son distintas')
            break
    # Keep local identities stable; choosing the referenced product as destination
    # often resolves this without a distributed migration of receipt/sync state.
    blockers.extend('El producto que desaparece conserva: ' + reason for reason in _local_deletion_blockers(source_id))
    products = _rows('products')
    if any(p.get('parent_product_id') not in (None, '', 0, '0') for p in (source, target)) or any(str(p.get('parent_product_id')) in (str(source_id), str(target_id)) for p in products):
        blockers.append('Hay relaciones entre productos padre e hijos')
    chores = _rows('chores')
    if any(str(value) == str(source_id) for row in chores for key, value in row.items() if 'product_id' in key):
        blockers.append('Hay tareas vinculadas que Grocy no migra')
    if source.get('userfields'):
        blockers.append('Hay campos personalizados en el producto que desaparece')
    snapshot = {'source': source, 'target': target, 'version': info.get('grocy_version'), 'products': products, 'chores': chores}
    for collection, _ in COLLECTIONS:
        rows = _rows(collection)
        if any('product_id' not in row for row in rows): raise ValueError('Referencia incompleta')
        if collection == 'recipes': snapshot['recipe_types'] = {str(row['id']): [row.get('name'), row.get('type')] for row in rows}
        snapshot[collection] = sorted((row for row in rows if str(row['product_id']) in (str(source_id), str(target_id))), key=lambda row: int(row['id']))
    for collection, _ in COLLECTIONS:
        for row in snapshot[collection]:
            for field in ('amount', 'product_amount'):
                if row.get(field) is not None and not Decimal(str(row[field])).is_finite():
                    blockers.append('Hay cantidades desconocidas en las referencias')
    shopping = snapshot['shopping_list']
    default_ids = {int(row['product_id']) for row in shopping if str(row.get('shopping_list_id')) == '1'}
    if {source_id, target_id} <= default_ids:
        blockers.append('Ambos productos están en la lista de compra: revisa sus filas antes de combinar')
    resolved = barcode_stock.grocy('GET', 'objects/quantity_unit_conversions_resolved')
    if not isinstance(resolved, list): raise ValueError('Conversiones no verificadas')
    snapshot['resolved'] = [row for row in resolved if str(row['product_id']) in (str(source_id), str(target_id))]
    for row in snapshot['resolved']:
        if str(row['from_qu_id']) == str(source['qu_id_stock']) and str(row['to_qu_id']) == str(target['qu_id_stock']):
            if Decimal(str(row['factor'])) != 1:
                blockers.append('La conversión efectiva entre las unidades debe ser 1')
    factors = {}
    for row in snapshot['quantity_unit_conversions']:
        edge = (int(row['from_qu_id']), int(row['to_qu_id']))
        factor = Decimal(str(row['factor']))
        if not factor.is_finite() or factor <= 0: raise ValueError('Conversión no válida')
        if edge in factors and factors[edge] != factor:
            blockers.append('Las conversiones de unidades tienen factores incompatibles')
        factors[edge] = factor
        if edge[0] == edge[1] and factor != 1:
            blockers.append('La conversión de la unidad consigo misma debe ser 1')
    for row in snapshot['stock']:
        amount = Decimal(str(row['amount']))
        if not amount.is_finite() or amount < 0: blockers.append('Hay stock negativo o desconocido')
    # Tare-weight products have additional amount semantics; do not guess.
    if any(barcode_stock._done(p.get('enable_tare_weight_handling', False)) for p in (source, target)):
        blockers.append('Los productos con tara requieren conciliación previa')
    snapshot['blockers'] = sorted(set(blockers))
    return snapshot


def merge_preview(source_id, target_id):
    snapshot = _audit(source_id, target_id)
    return _preview(snapshot)


def _preview(snapshot):
    def product(key):
        raw = snapshot[key]; pid = int(raw['id'])
        amount = sum((Decimal(str(row['amount'])) for row in snapshot['stock'] if int(row['product_id']) == pid), Decimal(0))
        factor = next((Decimal(str(row['factor'])) for row in snapshot['resolved'] if int(row['product_id']) == pid and str(row['from_qu_id']) == str(raw['qu_id_purchase']) and str(row['to_qu_id']) == str(raw['qu_id_stock'])), Decimal(1))
        return {'id': pid, 'name': raw['name'], 'stock_amount': str(amount), 'unit_id': int(raw['qu_id_stock']),
                'purchase_unit_id': int(raw['qu_id_purchase']), 'pack_size': float(factor),
                'barcodes': [row['barcode'] for row in snapshot['product_barcodes'] if int(row['product_id']) == pid]}
    source, target = product('source'), product('target')
    return {'source': source, 'target': target, 'source_variants': [], 'target_variants': [],
            'blockers': snapshot['blockers'], 'warnings': snapshot['blockers'],
            'can_merge': not snapshot['blockers'], 'merge_allowed': not snapshot['blockers'],
            'token': hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            'audit': {'collections': [{'collection': key, 'label': label, 'count': len(snapshot[key]), 'status': 'ok', 'references': []} for key, label in COLLECTIONS]}}


def merge_products(source_id, target_id, expected_source, expected_target, token):
    before = _audit(source_id, target_id)
    preview = _preview(before)
    if preview['source']['name'] != expected_source or preview['target']['name'] != expected_target or not hmac.compare_digest(preview['token'], token):
        raise barcode_stock.BarcodeError('Los productos o sus referencias han cambiado. Revisa de nuevo la combinación')
    if before['blockers']:
        raise barcode_stock.BarcodeError('No se pueden combinar: ' + '; '.join(before['blockers']))
    source_id, target_id = int(source_id), int(target_id)
    barcode_stock.grocy('POST', f'stock/products/{target_id}/merge/{source_id}')
    products = _rows('products')
    if any(int(p['id']) == source_id for p in products) or not any(int(p['id']) == target_id for p in products):
        raise RuntimeError('Combinación no verificada')
    saved = barcode_stock.grocy('GET', f'objects/products/{target_id}')
    if saved != before['target']: raise RuntimeError('Metadatos de destino no verificados')
    # Grocy rebuilds derived meal-plan recipes. Verify those by date/type/unit
    # totals; all user/history rows must retain their IDs and data.
    recipe_types = {str(row['id']): [row.get('name'), row.get('type')] for row in _rows('recipes')}
    def internal(row, kinds):
        kind = kinds.get(str(row.get('recipe_id')), [None, None])
        return (kind[1], kind[0], str(row.get('qu_id'))) if kind[1] in ('mealplan-day', 'mealplan-week') else None
    for collection, _ in COLLECTIONS:
        after = {int(row['id']): row for row in _rows(collection)}
        if any(str(row.get('product_id')) == str(source_id) for row in after.values()):
            raise RuntimeError('Quedan referencias de origen')
        if collection == 'quantity_unit_conversions':
            actual = {(int(row['from_qu_id']), int(row['to_qu_id']), Decimal(str(row['factor']))) for row in after.values() if int(row.get('product_id') or 0) == target_id}
            expected = {(int(row['from_qu_id']), int(row['to_qu_id']), Decimal(str(row['factor']))) for row in before[collection]}
            if not expected <= actual: raise RuntimeError('Conversiones no verificadas')
            continue
        if collection == 'recipes_pos':
            def totals(rows, kinds):
                result = {}
                for row in rows:
                    key = internal(row, kinds)
                    if key and int(row.get('product_id') or 0) in (source_id, target_id):
                        result[key] = result.get(key, Decimal(0)) + Decimal(str(row['amount']))
                return result
            if totals(before[collection], before['recipe_types']) != totals(after.values(), recipe_types):
                raise RuntimeError('Recetas derivadas no verificadas')
        for row in before[collection]:
            if collection == 'recipes_pos' and internal(row, before['recipe_types']): continue
            expected = {**row, 'product_id': target_id}
            actual = after.get(int(row['id']))
            if actual is None: raise RuntimeError('Referencia perdida')
            for key, value in expected.items():
                if key in ('amount', 'product_amount') and value is not None:
                    if Decimal(str(actual[key])) != Decimal(str(value)): raise RuntimeError('Cantidad no verificada')
                elif str(actual.get(key)) != str(value):
                    raise RuntimeError('Referencia no verificada')
    return {'merged': True, 'product_id': target_id, 'removed_product_id': source_id}
