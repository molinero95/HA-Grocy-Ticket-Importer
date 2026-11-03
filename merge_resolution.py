"""Explicit, journaled Grocy 4.7.1 unit normalization and reviewed final inventory.

Use native unit-change triggers before the native merge so historical unit prices
are divided as amounts are multiplied. Never edit remote SQLite or replay stages.
"""
import hashlib
import hmac
import json
import sqlite3
from contextlib import closing
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import barcode_stock
import merge_audit as native
import variant_catalog
from catalog_lifecycle import _local_deletion_blockers

UNIT_FIELDS = ('qu_id_stock', 'qu_id_purchase', 'qu_id_consume', 'qu_id_price')
PIECES = {'piece', 'pieces', 'unidad', 'unidades'}
PACKS = {'pack', 'paquete', 'envase'}


class PartialMerge(RuntimeError):
    def __init__(self, stage):
        self.stage = stage
        label = {'normalizar_unidades': 'normalizar las unidades', 'preparar_conversiones': 'preparar las conversiones', 'combinar_productos': 'combinar los productos', 'guardar_datos_finales': 'guardar los datos finales', 'ajustar_stock_final': 'ajustar el stock final', 'guardar_umbral': 'guardar el umbral'}.get(stage, 'completar la operación')
        super().__init__(f'La operación se interrumpió al {label}. Puede haber cambios aplicados. Comprueba ambos productos y el stock en Grocy antes de otra combinación.')


def number(value, *, minimum=Decimal(0), maximum=Decimal('1000000'), decimals=None):
    if isinstance(value, bool): raise ValueError('Introduce una cantidad válida')
    try: amount = Decimal(str(value).strip().replace(',', '.'))
    except (InvalidOperation, ValueError): raise ValueError('Introduce una cantidad válida') from None
    if not amount.is_finite() or not minimum <= amount <= maximum or (decimals is not None and amount.as_tuple().exponent < -decimals):
        raise ValueError('Revisa la cantidad, su equivalencia y los decimales')
    return amount


def text(amount):
    return format(Decimal(amount).normalize(), 'f')


def same(left, right):
    if left is None or right is None: return left is right
    a, b = Decimal(str(left)), Decimal(str(right))
    return a.is_finite() and b.is_finite() and abs(a - b) <= max(Decimal('0.00000001'), abs(b) * Decimal('0.000000000001'))


def threshold(pid):
    result = {'amount': '0', 'warning_enabled': True}
    path = Path(variant_catalog.CATALOG_DB)
    if not path.exists(): return result
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='stock_thresholds'").fetchone():
            column = 'warning_enabled' if 'warning_enabled' in {item[1] for item in db.execute('PRAGMA table_info(stock_thresholds)')} else '1'
            row = db.execute(f'SELECT amount, {column} FROM stock_thresholds WHERE product_id=?', (pid,)).fetchone()
            if row: result = {'amount': text(number(row[0])), 'warning_enabled': bool(row[1])}
    return result


def snapshot(source_id, target_id):
    data = native._audit(source_id, target_id, allow_unit_resolution=True)
    data['units'] = native._rows('quantity_units')
    data['global_conversions'] = [row for row in native._rows('quantity_unit_conversions') if row.get('product_id') in (None, '')]
    data['target_threshold'] = threshold(int(target_id))
    import importer
    from receipt_review import list_aliases
    data['receipt_aliases'] = [row for row in list_aliases(importer.DB_PATH) if row['product_id'] in (int(source_id), int(target_id))]
    if any(row['product_id'] == int(source_id) for row in data['receipt_aliases']):
        data['blockers'].append('El producto que desaparece conserva asociaciones de tickets; reasígnalas o conserva ese producto')
    return data


def options(source_id, target_id):
    data = snapshot(source_id, target_id)
    result = native._preview(data)
    result['units'] = [{'id': int(row['id']), 'name': row['name']} for row in data['units']]
    result['target_threshold'] = data['target_threshold']
    return result


def edges(rows, pid):
    result = {}
    for row in rows:
        if int(row.get('product_id') or 0) != pid: continue
        edge = int(row['from_qu_id']), int(row['to_qu_id'])
        factor = number(row['factor'], minimum=Decimal('0.000000000001'), maximum=Decimal('1000000000000'))
        if edge in result: raise ValueError('Hay conversiones duplicadas; revísalas antes de combinar')
        result[edge] = factor
    return result


def put_edge(graph, start, end, factor):
    if start == end:
        if factor != 1: raise ValueError('La equivalencia de una unidad consigo misma debe ser 1')
        return
    graph[start, end] = factor
    graph[end, start] = 1 / factor


def plan(data, resolution):
    if not isinstance(resolution, dict): raise ValueError('Indica los datos finales de combinación')
    units = {int(row['id']): row['name'] for row in data['units']}
    final_unit, purchase = resolution.get('unit_id'), resolution.get('purchase_unit_id')
    if type(final_unit) is not int or type(purchase) is not int or final_unit not in units or purchase not in units:
        raise ValueError('Selecciona las unidades finales')
    if units[final_unit].casefold() in PACKS: raise ValueError('Pack es una unidad de compra; el stock debe estar en piezas u otra unidad')
    name = resolution.get('final_name')
    if not isinstance(name, str) or not name.strip() or len(name) > 200: raise ValueError('Indica un nombre final de hasta 200 caracteres')
    name = name.strip()
    source, target = data['source'], data['target']
    ids = {int(source['id']), int(target['id'])}
    if any(int(p['id']) not in ids and str(p['name']).strip().casefold() == name.casefold() for p in data['products']):
        raise ValueError('El nombre final ya pertenece a otro producto')
    factors = {int(data[key]['id']): number(resolution.get(key + '_factor'), minimum=Decimal('0.000001'), decimals=6) for key in ('source', 'target')}
    stock = number(resolution.get('final_stock'), decimals=2)
    pack = number(resolution.get('pack_size'), minimum=Decimal(1), maximum=Decimal(1000), decimals=0)
    if purchase == final_unit:
        if pack != 1: raise ValueError('La compra en la unidad de stock tiene equivalencia 1')
    elif units[purchase].casefold() not in PACKS or units[final_unit].casefold() not in PIECES:
        raise ValueError('Pack solo se usa para comprar un producto cuyo stock está en piezas')
    blockers = list(data['blockers'])
    for collection in ('stock', 'stock_log'):
        for row in data[collection]:
            if row.get('price') is not None: number(row['price'], minimum=Decimal('-1000000000000'), maximum=Decimal('1000000000000'))
    graphs = {}
    for key in ('source', 'target'):
        raw = data[key]; pid = int(raw['id']); old_unit = int(raw['qu_id_stock']); factor = factors[pid]
        if old_unit == final_unit and factor != 1: raise ValueError('La equivalencia de la misma unidad debe ser 1')
        if barcode_stock._done(raw.get('no_own_stock', False)): blockers.append('Hay un producto que no admite stock propio')
        if old_unit != final_unit and Decimal(str(raw.get('min_stock_amount') or 0)) != 0:
            blockers.append('Revisa el mínimo nativo de Grocy antes de cambiar la unidad de stock')
        if old_unit != final_unit and any(row['product_id'] == pid for row in data['receipt_aliases']):
            blockers.append('Hay asociaciones de tickets que conservan la unidad anterior; revísalas antes de cambiarla')
        if old_unit != final_unit and key == 'target':
            blockers.extend('Para cambiar la unidad del producto conservado, revisa: ' + reason for reason in _local_deletion_blockers(pid, allow_completed_receipts=True))
            if any(str(value) == str(pid) for row in data['chores'] for field, value in row.items() if 'product_id' in field):
                blockers.append('Hay tareas vinculadas a la unidad del producto conservado')
        if old_unit != final_unit and any(int(row['product_id']) == pid and Decimal(str(row.get('amount_autoadded') or 0)) != 0 for row in data['shopping_list']):
            blockers.append('Hay cantidades automáticas de compra que necesitan revisión previa')
        graph = edges(data['quantity_unit_conversions'], pid)
        if purchase != final_unit and (purchase, final_unit) in graph and not same(graph[purchase, final_unit], pack):
            if any(int(row['product_id']) == pid and str(row.get('qu_id')) == str(purchase) for collection in ('product_barcodes', 'recipes_pos') for row in data[collection]):
                blockers.append('Hay códigos o recetas que usan la equivalencia de envase anterior; revísalos antes de cambiarla')
        put_edge(graph, old_unit, final_unit, factor)
        if purchase != final_unit: put_edge(graph, purchase, final_unit, pack)
        graphs[pid] = graph
    first, second = graphs[int(source['id'])], graphs[int(target['id'])]
    for edge in first.keys() & second.keys():
        if not same(first[edge], second[edge]): blockers.append('Hay conversiones adicionales incompatibles; revisa sus equivalencias en Grocy')
    total = sum(Decimal(str(row['amount'])) * factors[int(row['product_id'])] for row in data['stock'])
    if total > 1000000: raise ValueError('El stock convertido supera el límite admitido; revisa las equivalencias')
    current_threshold = Decimal(data['target_threshold']['amount'])
    suggested_threshold = (current_threshold * factors[int(target['id'])]).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    final_threshold = number(resolution.get('threshold_amount', text(suggested_threshold)), decimals=2)
    normalized = {'final_name': name, 'unit_id': final_unit, 'purchase_unit_id': purchase,
                  'source_factor': text(factors[int(source['id'])]), 'target_factor': text(factors[int(target['id'])]),
                  'pack_size': text(pack), 'final_stock': text(stock), 'threshold_amount': text(final_threshold)}
    return {'resolution': normalized, 'factors': factors, 'graphs': graphs, 'blockers': sorted(set(blockers)),
            'combined_stock': text(total), 'stock_correction': text(stock - total), 'unit_name': units[final_unit]}


def review(source_id, target_id, resolution):
    data = snapshot(source_id, target_id)
    prepared = plan(data, resolution)
    result = native._preview(data)
    result.update({key: prepared[key] for key in ('resolution', 'blockers', 'combined_stock', 'stock_correction', 'unit_name')})
    result['can_merge'] = not prepared['blockers']
    result['token'] = hashlib.sha256(json.dumps({'snapshot': data, 'resolution': prepared['resolution']}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return result


def _upsert(pid, start, end, factor):
    if start == end: return
    rows = native._rows('quantity_unit_conversions')
    found = [row for row in rows if str(row.get('product_id')) == str(pid) and int(row['from_qu_id']) == start and int(row['to_qu_id']) == end]
    if len(found) > 1: raise RuntimeError('Duplicated conversion')
    if not found:
        barcode_stock.grocy('POST', 'objects/quantity_unit_conversions', {'product_id': pid, 'from_qu_id': start, 'to_qu_id': end, 'factor': float(factor)})
    elif not same(found[0]['factor'], factor):
        barcode_stock.grocy('PUT', 'objects/quantity_unit_conversions/' + str(found[0]['id']), {'factor': float(factor)})
    resolved = barcode_stock.grocy('GET', 'objects/quantity_unit_conversions_resolved')
    direct = [row for row in resolved if str(row['product_id']) == str(pid) and int(row['from_qu_id']) == start and int(row['to_qu_id']) == end]
    if len(direct) != 1 or not same(direct[0]['factor'], factor): raise RuntimeError('Conversion not verified')


def _verify_normalization(before, after, pid, factor):
    """Check native unit-change effects before any irreversible native merge."""
    def derived_totals(data, converted=False):
        totals = {}
        for row in data['recipes_pos']:
            kind = data['recipe_types'].get(str(row.get('recipe_id')), [None, None])
            if kind[1] not in ('mealplan-day', 'mealplan-week'): continue
            identity = (kind[1], kind[0], int(row['product_id']))
            amount = Decimal(str(row['amount']))
            if converted and identity[2] == pid: amount *= factor
            totals[identity] = totals.get(identity, Decimal(0)) + amount
        return totals
    expected, actual = derived_totals(before, True), derived_totals(after)
    if expected.keys() != actual.keys() or any(not same(actual[key], value) for key, value in expected.items()):
        raise RuntimeError('Derived recipe conversion not verified')
    for collection, _ in native.COLLECTIONS:
        if collection == 'quantity_unit_conversions': continue
        rows = {int(row['id']): row for row in after[collection]}
        for row in before[collection]:
            if int(row['product_id']) != pid: continue
            if collection == 'recipes_pos' and before['recipe_types'].get(str(row.get('recipe_id')), [None, None])[1] in ('mealplan-day', 'mealplan-week'):
                continue  # Native merge audit independently verifies rebuilt derived recipes.
            actual = rows.get(int(row['id']))
            if actual is None: raise RuntimeError('A reference disappeared during normalization')
            for field, value in row.items():
                expected = value
                if value is not None and ((field == 'amount' and collection in ('stock', 'stock_log', 'recipes_pos', 'shopping_list')) or (field == 'product_amount' and collection == 'meal_plan' and row.get('type') == 'product')):
                    expected = Decimal(str(value)) * factor
                if value is not None and field == 'price' and collection in ('stock', 'stock_log'):
                    expected = Decimal(str(value)) / factor
                if field in ('amount', 'product_amount', 'price') and value is not None:
                    if not same(actual.get(field), expected): raise RuntimeError('Converted amount or price not verified')
                elif str(actual.get(field)) != str(expected): raise RuntimeError('Reference metadata changed')


def commit(source_id, target_id, expected_source, expected_target, resolution, token):
    before = snapshot(source_id, target_id)
    try:
        prepared = plan(before, resolution)
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise barcode_stock.BarcodeError(str(exc)) from exc
    digest = hashlib.sha256(json.dumps({'snapshot': before, 'resolution': prepared['resolution']}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if before['source']['name'] != expected_source or before['target']['name'] != expected_target or not hmac.compare_digest(digest, token):
        raise barcode_stock.BarcodeError('Los productos, el stock o sus referencias han cambiado. Revisa de nuevo la combinación')
    if prepared['blockers']: raise barcode_stock.BarcodeError('No se pueden combinar: ' + '; '.join(prepared['blockers']))
    source_id, target_id = int(source_id), int(target_id)
    spec = prepared['resolution']; unit = spec['unit_id']; purchase = spec['purchase_unit_id']
    stage = 'normalizar_unidades'
    try:
        for key in ('source', 'target'):
            raw = before[key]; pid = int(raw['id']); old_unit = int(raw['qu_id_stock']); factor = prepared['factors'][pid]
            current = native._audit(source_id, target_id, allow_unit_resolution=True)
            if old_unit != unit: _upsert(pid, old_unit, unit, factor)
            if any(int(raw[field]) != unit for field in UNIT_FIELDS):
                barcode_stock.grocy('PUT', f'objects/products/{pid}', {field: unit for field in UNIT_FIELDS})
            if old_unit != unit:
                # Grocy's BEFORE product trigger scales meal plans, rebuilds their
                # derived recipes, then scales recipes again. Reapply the SAME
                # authoritative plan quantity after the product unit is saved,
                # rebuilding derived recipes in the final unit, exactly once.
                for row in current['meal_plan']:
                    if int(row['product_id']) == pid and row.get('type') == 'product':
                        barcode_stock.grocy('PUT', 'objects/meal_plan/' + str(row['id']), {'product_amount': float(Decimal(str(row['product_amount'])) * factor)})
            after = native._audit(source_id, target_id, allow_unit_resolution=True)
            _verify_normalization(current, after, pid, factor)
            saved = after[key]
            if any(int(saved[field]) != unit for field in UNIT_FIELDS): raise RuntimeError('Unit metadata not verified')
        stage = 'preparar_conversiones'
        if purchase != unit:
            for pid in (source_id, target_id): _upsert(pid, purchase, unit, Decimal(spec['pack_size']))
        rows = native._rows('quantity_unit_conversions')
        target_edges = edges(rows, target_id)
        for row in rows:
            if int(row.get('product_id') or 0) != source_id: continue
            edge = int(row['from_qu_id']), int(row['to_qu_id'])
            if edge not in target_edges: continue
            if not same(row['factor'], target_edges[edge]): raise RuntimeError('Conflicting conversion after normalization')
            remaining = native._rows('quantity_unit_conversions')
            if any(int(item['id']) == int(row['id']) for item in remaining):
                barcode_stock.grocy('DELETE', 'objects/quantity_unit_conversions/' + str(row['id']))
        stage = 'combinar_productos'
        checked = native.merge_preview(source_id, target_id)
        if not checked['can_merge']: raise RuntimeError('Native merge prerequisites changed')
        native.merge_products(source_id, target_id, expected_source, expected_target, checked['token'])
        stage = 'guardar_datos_finales'
        expected = barcode_stock.grocy('GET', f'objects/products/{target_id}')
        changes = {'name': spec['final_name'], 'qu_id_purchase': purchase}
        if any(str(expected[field]) != str(value) for field, value in changes.items()):
            barcode_stock.grocy('PUT', f'objects/products/{target_id}', changes)
        saved = barcode_stock.grocy('GET', f'objects/products/{target_id}')
        if any(str(saved.get(field)) != str(value) for field, value in {**expected, **changes}.items()): raise RuntimeError('Final metadata not verified')
        stage = 'ajustar_stock_final'
        current = barcode_stock.grocy('GET', f'stock/products/{target_id}')
        if not same(current['stock_amount'], prepared['combined_stock']): raise RuntimeError('Merged stock changed before correction')
        history = [row for row in native._rows('stock_log') if int(row['product_id']) == target_id]
        if Decimal(spec['final_stock']) != Decimal(prepared['combined_stock']):
            barcode_stock.grocy('POST', f'stock/products/{target_id}/inventory', {'new_amount': float(Decimal(spec['final_stock'])), 'best_before_date': '2999-12-31', 'location_id': int(saved['location_id']), 'note': 'Ajuste final de combinación revisada en Despensa'})
        final = barcode_stock.grocy('GET', f'stock/products/{target_id}')
        if not same(final['stock_amount'], spec['final_stock']): raise RuntimeError('Final stock not verified')
        after_history = {int(row['id']): row for row in native._rows('stock_log')}
        if any(after_history.get(int(row['id'])) != row for row in history): raise RuntimeError('Prior history changed during correction')
        stage = 'guardar_umbral'
        if spec['threshold_amount'] != before['target_threshold']['amount']:
            from stock_thresholds import save_threshold
            save_threshold(target_id, spec['threshold_amount'], before['target_threshold']['amount'], before['target_threshold']['warning_enabled'], before['target_threshold']['warning_enabled'])
    except Exception as exc:
        raise PartialMerge(stage) from exc
    return {'merged': True, 'product_id': target_id, 'removed_product_id': source_id, 'final_stock': spec['final_stock'], 'unit_id': unit}
