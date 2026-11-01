"""Create from unknown Alexa entries; preserve row identity/amount/note, never stock."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
import barcode_stock
import shopping_match_queue as queue
with patch.dict(os.environ, WEB_PASSWORD='test-password', WEB_SESSION_SECRET='test-secret-key'):
    import web


class ShoppingCreationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.path = self.root / 'queue.sqlite3'
        self.products = [{'id': 7, 'name': 'Producto distinto', 'active': 1, 'qu_id_stock': 2}]
        self.rows = [{'id': 10, 'shopping_list_id': 1, 'product_id': None, 'note': 'Gel Alexa', 'amount': 2.5, 'qu_id': None, 'done': 0}]
        self.existing = self.lose_create = self.lose_association = False
        self.puts = 0
        for mock in (patch.object(queue, 'DEFAULT_PATH', self.path), patch.object(web, 'INGRESS_MODE', True),
                     patch.dict(web.app.config, SECRET_KEY='creation-key'),
                     patch.dict(os.environ, WEB_PASSWORD='test-password', STOCK_COMMAND_DB=str(self.root / 'commands.sqlite3')),
                     patch.object(barcode_stock, 'grocy', side_effect=self.grocy),
                     patch.object(barcode_stock, 'create_catalog_product', side_effect=self.create),
                     patch('shopping_sync_adapters.ha_service', side_effect=AssertionError('No direct Alexa writes'))):
            value = mock.start(); self.addCleanup(mock.stop)
            if getattr(mock, 'attribute', None) == 'create_catalog_product': self.creator = value
        queue.refresh(self.path, ['Gel Alexa'], self.products)
        self.client = web.app.test_client()
        self.headers = {'X-CSRF-Token': self.client.get('/api/v1/auth/status').json['csrf_token']}
        self.url = '/api/v1/alexa/matches/gel%20alexa/'

    def create(self, name, barcode, unit, initial, **kwargs):
        self.assertEqual(initial, '0')
        if self.existing: return {'created': False, 'product_id': 7, 'name': self.products[0]['name']}
        self.products.append({'id': 8, 'name': name, 'active': 1, 'qu_id_stock': unit})
        if self.lose_create: raise ConnectionError('private upstream')
        return {'created': True, 'product_id': 8, 'name': name}

    def grocy(self, method, path, body=None):
        if method == 'GET':
            if path == 'objects/products': return copy.deepcopy(self.products)
            if path == 'objects/shopping_list': return copy.deepcopy(self.rows)
            if path.startswith('objects/shopping_list/'):
                return copy.deepcopy(next(row for row in self.rows if row['id'] == int(path.rsplit('/', 1)[1])))
        if method == 'PUT' and path == 'objects/shopping_list/10':
            self.puts += 1; self.rows[0].update(body)
            if self.lose_association: raise ConnectionError('private upstream')
            return {}
        if method == 'POST' and path == 'objects/shopping_list':
            self.rows.append({'id': 11, 'done': 0, **body}); return {'created_object_id': 11}
        raise AssertionError('Unexpected or stock mutation: ' + method + ' ' + path)

    def payload(self):
        context = self.client.get(self.url + 'create-context')
        self.assertEqual(context.status_code, 200, context.json)
        return {'expected_name': context.json['name'], 'generation': context.json['generation'],
                'product': {'name': 'Jabón neutro de ducha', 'unit_id': 2, 'initial_stock': '0', 'barcode': '', 'pack_size': '1'}, 'operation_id': str(uuid.uuid4())}

    def test_unknown_alexa_without_suggestions_can_create_and_associate_once(self):
        self.assertEqual(queue.pending(self.path)[0]['candidates'], [])
        payload = self.payload()
        for _ in range(2):
            response = self.client.post(self.url + 'create-product', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 201, response.json)
            self.assertTrue(response.json['associated'])
        self.creator.assert_called_once()
        self.assertEqual(self.puts, 1)
        self.assertEqual((self.rows[0]['id'], self.rows[0]['amount'], self.rows[0]['note'], self.rows[0]['product_id']), (10, 2.5, 'Gel Alexa', 8))
        choices = queue.resolved_choices(self.path, ['Gel Alexa'], self.products)
        self.assertEqual(choices['gel alexa']['product_id'], 8)
        queue.refresh(self.path, ['Gel Alexa'], self.products)
        self.assertEqual(queue.resolved_choices(self.path, ['Gel Alexa'], self.products)['gel alexa']['product_id'], 8)

    def test_existing_product_needs_explicit_association_without_duplicate_or_stock(self):
        self.existing = True
        response = self.client.post(self.url + 'create-product', json=self.payload(), headers=self.headers)
        self.assertEqual(response.status_code, 202, response.json)
        self.assertFalse(response.json['created']); self.assertFalse(response.json['associated'])
        self.assertEqual(self.puts, 0)
        context = self.client.get(self.url + 'create-context').json
        self.assertTrue(context['can_associate']); self.assertFalse(context['can_create'])
        response = self.client.post(self.url + 'choose', json={'product_id': 7, 'operation_id': str(uuid.uuid4())}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual((len(self.rows), self.rows[0]['amount'], self.rows[0]['product_id']), (1, 2.5, 7))

    def test_lost_association_can_be_completed_after_reading_without_recreating_or_rewriting_row(self):
        self.lose_association = True
        response = self.client.post(self.url + 'create-product', json=self.payload(), headers=self.headers)
        self.assertEqual(response.status_code, 202, response.json)
        self.assertTrue(response.json['association_uncertain'])
        self.assertEqual(self.puts, 1)
        context = self.client.get(self.url + 'create-context').json
        self.assertTrue(context['can_associate'])
        self.assertEqual(queue.resolved_choices(self.path, ['Gel Alexa'], self.products)['gel alexa']['product_id'], 8)
        response = self.client.post(self.url + 'choose', json={'product_id': 8, 'operation_id': str(uuid.uuid4())}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        self.creator.assert_called_once(); self.assertEqual(self.puts, 1)
        self.assertTrue(self.client.get(self.url + 'create-context').json['associated'])

    def test_uncertain_creation_never_replays_and_error_is_sanitized(self):
        self.lose_create = True; payload = self.payload()
        for expected in (502, 409):
            response = self.client.post(self.url + 'create-product', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, expected, response.json)
            self.assertNotIn('private upstream', response.get_data(as_text=True))
        self.creator.assert_called_once(); self.assertEqual(self.puts, 0)

    def test_auth_csrf_stale_generation_and_nonzero_initial_stock_precede_creation(self):
        with patch.object(web, 'INGRESS_MODE', False): self.assertEqual(self.client.get(self.url + 'create-context').status_code, 401)
        payload = self.payload()
        self.assertEqual(self.client.post(self.url + 'create-product', json=payload).status_code, 403)
        bad = {**payload, 'product': {**payload['product'], 'initial_stock': '1'}}
        self.assertEqual(self.client.post(self.url + 'create-product', json=bad, headers=self.headers).status_code, 400)
        payload['generation'] += 1
        self.assertEqual(self.client.post(self.url + 'create-product', json=payload, headers=self.headers).status_code, 409)
        self.creator.assert_not_called()

    def test_created_binding_does_not_leak_to_another_source_episode(self):
        payload = self.payload()
        self.assertEqual(self.client.post(self.url + 'create-product', json=payload, headers=self.headers).status_code, 201)
        queue.refresh(self.path, [], self.products)
        queue.refresh(self.path, ['Gel Alexa'], self.products)
        entry = queue.pending(self.path)[0]
        self.assertIsNone(entry['created_product_id']); self.assertIsNone(entry['selected_product_id'])
        self.assertEqual(entry['generation'], 2)
        self.assertEqual(queue.resolved_choices(self.path, ['Gel Alexa'], self.products), {})

    def test_creation_context_accepts_names_with_slashes_from_alexa(self):
        self.rows[0]['note'] = 'Gel / Alexa'
        queue.refresh(self.path, ['Gel / Alexa'], self.products)
        response = self.client.get('/api/v1/alexa/matches/gel%20%2F%20alexa/create-context')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['name'], 'Gel / Alexa')
        self.creator.assert_not_called()
