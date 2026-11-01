"""Archive/restore and guarded deletion of unused archived products; retain history."""
from decimal import Decimal
import barcode_stock


def is_active(product):
    return barcode_stock._done(product.get("active", True))


def set_active(product_id, expected_name, active):
    pid = int(product_id)
    product = barcode_stock.grocy("GET", f"objects/products/{pid}")
    if not isinstance(product, dict) or product.get("name") != expected_name:
        raise barcode_stock.BarcodeError("El producto ha cambiado. Actualiza la ficha")
    if not active:
        stock = barcode_stock.grocy("GET", f"stock/products/{pid}")
        amount = Decimal(str(stock["stock_amount"]))
        if not amount.is_finite() or amount != 0:
            raise barcode_stock.BarcodeError("Solo se puede archivar un producto sin existencias")
        # Preserve historical links, but refuse to hide an active dependency.
        for collection, field in (("shopping_list", "product_id"), ("recipes_pos", "product_id"),
                                  ("recipes", "product_id"), ("products", "parent_product_id"),
                                  ("meal_plan", "product_id")):
            rows = barcode_stock.grocy("GET", "objects/" + collection)
            if not isinstance(rows, list):
                raise barcode_stock.BarcodeError("No se pudieron comprobar las referencias del producto")
            if any(str(row.get(field)) == str(pid) for row in rows):
                labels = {"shopping_list": "lista de la compra", "recipes_pos": "recetas", "recipes": "recetas", "products": "productos dependientes", "meal_plan": "plan de comidas"}
                raise barcode_stock.BarcodeError("El producto sigue en uso: " + labels[collection])
    barcode_stock.grocy("PUT", f"objects/products/{pid}", {"active": 1 if active else 0})
    saved = barcode_stock.grocy("GET", f"objects/products/{pid}")
    if is_active(saved) != active:
        raise RuntimeError("No se pudo verificar el estado del producto")
    return {"product_id": pid, "active": active}


def archived_inventory():
    products = barcode_stock.grocy("GET", "objects/products")
    if not isinstance(products, list):
        raise barcode_stock.BarcodeError("No se pudo consultar el catálogo")
    ids = {int(p["id"]) for p in products if not is_active(p)}
    return [{**row, "shopping_amount": "0", "shopping_step": "1", "shopping_unit": row["unit"],
             "shopping_can_subtract": False} for row in barcode_stock.inventory_snapshot(include_archived=True)
            if row["id"] in ids]


def _local_deletion_blockers(pid):
    """Inspect owned local state read-only; retain all journals and metadata."""
    import json
    import os
    import sqlite3
    from contextlib import closing
    from pathlib import Path
    import importer
    import shopping_match_queue as queue
    import variant_catalog
    from shopping_sync_worker import STATE_V2
    blockers = []

    def read(path, inspect):
        path = Path(path)
        if path.exists():
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                inspect(db, tables)

    def variants(db, tables):
        if 'product_variants' in tables and db.execute(
                'SELECT 1 FROM product_variants v JOIN generic_products g ON g.id=v.generic_id WHERE g.grocy_product_id=? LIMIT 1', (pid,)).fetchone():
            blockers.append('variantes asociadas')
    read(variant_catalog.CATALOG_DB, variants)

    def receipts(db, tables):
        if 'receipt_items' in tables and db.execute('SELECT 1 FROM receipt_items WHERE product_id=? LIMIT 1', (pid,)).fetchone():
            blockers.append('historial de tickets')
    read(os.environ.get('GROCY_IMPORT_DB', importer.DB_PATH), receipts)

    def alexa(db, tables):
        if 'alexa_aliases' in tables and db.execute('SELECT 1 FROM alexa_aliases WHERE product_id=? LIMIT 1', (pid,)).fetchone():
            blockers.append('alias de Alexa')
        if 'pending_matches' in tables:
            db.row_factory = sqlite3.Row
            for row in db.execute('SELECT * FROM pending_matches WHERE active=1'):
                if str(row['selected_product_id']) == str(pid):
                    blockers.append('una elección pendiente de Alexa')
                if 'removal_json' in row.keys() and row['removal_json']:
                    if str(json.loads(row['removal_json']).get('product_id')) == str(pid):
                        blockers.append('una retirada pendiente de Alexa')
    paths = {queue.DEFAULT_PATH, queue.BASE_PATH}
    paths.update(queue.BASE_PATH.parent.glob(queue.BASE_PATH.stem + '-*' + queue.BASE_PATH.suffix))
    for path in paths:
        read(path, alexa)
    checkpoints = {STATE_V2, *STATE_V2.parent.glob('shopping-sync-*-identity-v2.json')}
    for path in checkpoints:
        if path.exists():
            from shopping_identity_runtime import load_identity_state
            state = load_identity_state(path)
            if 'p:' + str(pid) in state['keys'] or pid in state['bindings'].values():
                blockers.append('sincronización de Alexa aún vinculada')
    return sorted(set(blockers))


def deletion_preview(product_id):
    """Audit Grocy 4.7.1 cascade targets before offering irreversible deletion."""
    import hashlib
    import json
    pid = int(product_id)
    product = barcode_stock.grocy('GET', f'objects/products/{pid}')
    if not isinstance(product, dict) or int(product.get('id', 0)) != pid or not isinstance(product.get('name'), str):
        raise barcode_stock.BarcodeError('No se pudo verificar el producto')
    info = barcode_stock.grocy('GET', 'system/info')
    if not isinstance(info, dict) or not isinstance(info.get('grocy_version'), dict):
        raise ValueError('No se pudo comprobar la versión de Grocy')
    version = info['grocy_version'].get('Version')
    blockers = []
    if version != '4.7.1':
        blockers.append('una versión de Grocy cuyas cascadas de borrado aún no se han verificado')
    if is_active(product):
        blockers.append('el producto no está archivado')
    stock = barcode_stock.grocy('GET', f'stock/products/{pid}')
    amount = Decimal(str(stock['stock_amount']))
    if not amount.is_finite() or amount != 0:
        blockers.append('existencias distintas de cero')
    snapshot = {'product': product, 'stock': str(amount), 'grocy_version': version}
    checks = [('stock', 'product_id', 'lotes de existencias'),
              ('stock_log', 'product_id', 'historial de movimientos'),
              ('shopping_list', 'product_id', 'referencias en listas de compra'),
              ('recipes_pos', 'product_id', 'ingredientes de recetas'),
              ('recipes', 'product_id', 'recetas vinculadas'),
              ('meal_plan', 'product_id', 'plan de comidas'),
              ('products', 'parent_product_id', 'productos dependientes'),
              ('product_barcodes', 'product_id', None),
              ('quantity_unit_conversions', 'product_id', None)]
    for collection, field, reason in checks:
        rows = barcode_stock.grocy('GET', 'objects/' + collection)
        if not isinstance(rows, list) or any(not isinstance(row, dict) or field not in row or 'id' not in row for row in rows):
            raise ValueError('No se pudieron comprobar las referencias')
        linked = sorted((row for row in rows if str(row.get(field)) == str(pid)), key=lambda row: int(row['id']))
        snapshot[collection] = linked
        if reason and linked:
            blockers.append(reason)
    blockers.extend(_local_deletion_blockers(pid))
    snapshot['local_blockers'] = blockers
    token = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'product_id': pid, 'name': product['name'], 'allowed': not blockers,
            'blockers': blockers, 'token': token,
            'barcode_count': len(snapshot['product_barcodes']),
            'conversion_count': len(snapshot['quantity_unit_conversions'])}


def delete_archived(product_id, expected_name, token):
    """Reaudit at dispatch. Caller holds app/worker locks and at-most-once journal."""
    import hmac
    preview = deletion_preview(product_id)
    if preview['name'] != expected_name or not hmac.compare_digest(preview['token'], token):
        raise barcode_stock.BarcodeError('El producto o sus referencias han cambiado. Vuelve a revisar el borrado')
    if not preview['allowed']:
        raise barcode_stock.BarcodeError('No se puede eliminar: ' + ', '.join(preview['blockers']))
    pid = int(product_id)
    barcode_stock.grocy('DELETE', f'objects/products/{pid}')
    products = barcode_stock.grocy('GET', 'objects/products')
    if not isinstance(products, list) or any(int(row['id']) == pid for row in products):
        raise RuntimeError('No se pudo verificar la eliminación')
    return {'deleted': True, 'product_id': pid}
