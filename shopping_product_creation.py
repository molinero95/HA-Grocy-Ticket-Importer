"""Explicit creation from an Alexa/shopping review, without stock writes."""
import uuid
import barcode_stock
from shopping_choice_conversion import _default_rows, manual_choice
from shopping_sync import normalize
from stock_commands import execute_once


def creation_context(grocy, queue, path, key):
    key = normalize(key)
    products = grocy('GET', 'objects/products')
    if not isinstance(products, list): raise ValueError('No se pudo verificar el catálogo')
    products = [product for product in products if queue._active(product)]
    rows = _default_rows(grocy)
    queue.refresh_catalog(path, products, [row.get('note') or '' for row in rows if not row.get('product_id')])
    entry = next((row for row in queue.pending(path) if row['key'] == key and not row.get('removed')), None)
    if entry is None: raise ValueError('El artículo ya no está disponible. Actualiza la lista')
    notes = [row for row in rows if not row.get('product_id') and normalize(row.get('note') or '') == key]
    prepared = entry.get('created_product_id')
    canonical = [row for row in rows if prepared and int(row.get('product_id') or 0) == prepared]
    attached = next((row for row in rows if int(row['id']) == entry.get('shopping_entry_id')), None)
    can_create = not prepared and entry.get('selected_product_id') is None and not (attached and attached.get('product_id')) and len(notes) <= 1 and not (attached and normalize(attached.get('note') or '') != key)
    can_associate = bool(prepared and len(canonical) <= 1 and len(notes) <= 1 and not (canonical and notes) and not (attached and attached.get('product_id') and int(attached['product_id']) != prepared))
    product = next((p for p in products if int(p['id']) == prepared and queue._active(p)), None)
    if prepared and not product: can_associate = False
    associated = bool(canonical and entry.get('dismissed') and entry.get('shopping_entry_id') == int(canonical[0]['id']))
    return {'key': key, 'name': entry['name'], 'generation': entry['generation'], 'can_create': can_create,
            'product_id': prepared, 'product_name': product['name'] if product else None,
            'can_associate': can_associate, 'associated': associated}


def create_for_shopping(grocy, queue, path, key, payload):
    """Journal creation + initial association; partial results never recreate a product."""
    key = normalize(key)
    operation_id = payload.get('operation_id')
    def apply():
        context = creation_context(grocy, queue, path, key)
        if context['generation'] != payload['generation'] or context['name'] != payload['expected_name'] or not context['can_create']:
            return {'status': 409, 'body': {'error': 'El artículo ha cambiado o ya tiene un producto preparado. Revisa la lista'}}
        product = payload['product']
        try:
            result = barcode_stock.create_catalog_product(product['name'], product.get('barcode', ''), product['unit_id'], '0', pack_size=product.get('pack_size', '1'))
        except barcode_stock.BarcodeError as exc:
            return {'status': 409, 'body': {'error': str(exc)}}
        response = {**result, 'associated': False}
        try:
            queue.prepare_created_product(path, key, context['generation'], int(result['product_id']))
            products = grocy('GET', 'objects/products')
            queue.refresh_catalog(path, products, [context['name']])
            if result['created']:
                # The user explicitly requested creation AND association. Keep this
                # intended identity durable before a possibly uncertain remote PUT.
                queue.choose(path, key, result['product_id'])
                association_id = str(uuid.uuid5(uuid.NAMESPACE_URL, operation_id + ':associate'))
                saved = manual_choice(grocy, queue, path, key, int(result['product_id']), association_id)
                response.update(associated=True, item_id=saved['item_id'])
        except Exception:
            response['association_uncertain'] = True
        return {'status': 201 if response['associated'] else 202, 'body': response}
    return execute_once(operation_id, {'kind': 'shopping-product-creation', 'scope': str(path), 'key': key, **payload}, apply)
