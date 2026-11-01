"""Native transaction dispatch, preserved references and no automatic replay."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
import barcode_stock
import merge_audit as merge
import shopping_match_queue as queue
with patch.dict(os.environ, WEB_PASSWORD='test-password', WEB_SESSION_SECRET='test-secret-key'):
    import web


class MergeFixture:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = {'id': 1, 'name': 'Leche prueba', 'active': 1, 'qu_id_stock': 2, 'qu_id_purchase': 2, 'qu_id_consume': 2, 'qu_id_price': 2, 'parent_product_id': None, 'userfields': None}
        self.target = {**self.source, 'id': 2, 'name': 'Leche pruebas'}
        self.products = [self.source, self.target]
        self.rows = {name: [] for name, _ in merge.COLLECTIONS}
        self.rows['stock'] = [{'id': 10, 'product_id': 1, 'amount': 2, 'price': 3, 'stock_id': 'lot-a'}, {'id': 11, 'product_id': 2, 'amount': 3, 'price': 4, 'stock_id': 'lot-b'}]
        self.rows['stock_log'] = [{'id': 20, 'product_id': 1, 'amount': 2, 'price': 3, 'note': 'keep history'}]
        self.rows['product_barcodes'] = [{'id': 30, 'product_id': 1, 'barcode': '8419876543210'}]
        self.rows['quantity_unit_conversions'] = [{'id': 40, 'product_id': 1, 'from_qu_id': 2, 'to_qu_id': 2, 'factor': 1}]
        self.chores = []
        self.version = '4.7.1'
        self.uncertain = self.corrupt = False
        self.local = patch('catalog_lifecycle._local_deletion_blockers', return_value=[])
        # merge imported the guard explicitly; patch at the use site.
        for mock in (patch.object(merge, '_local_deletion_blockers', return_value=[]),
                     patch.object(queue, 'DEFAULT_PATH', self.root / 'queue.sqlite3'),
                     patch.dict(os.environ, STOCK_COMMAND_DB=str(self.root / 'commands.sqlite3'), WEB_PASSWORD='test-password'),
                     patch.object(barcode_stock, 'grocy', side_effect=self.grocy)):
            result = mock.start(); self.addCleanup(mock.stop)
            if getattr(mock, 'attribute', None) == 'grocy': self.http = result
            if getattr(mock, 'attribute', None) == '_local_deletion_blockers': self.local_guard = result

    def grocy(self, method, path, body=None):
        if method == 'POST':
            self.assertEqual(path, 'stock/products/2/merge/1')
            self.products = [self.target]
            for rows in self.rows.values():
                for row in rows:
                    if row['product_id'] == 1: row['product_id'] = 2
            if self.corrupt: self.rows['stock_log'][0]['amount'] = 999
            if self.uncertain: raise ConnectionError('private upstream address')
            return {}
        self.assertEqual(method, 'GET')
        if path == 'system/info': return {'grocy_version': {'Version': self.version}}
        if path == 'objects/products/1': return copy.deepcopy(self.source)
        if path == 'objects/products/2': return copy.deepcopy(self.target)
        if path == 'objects/products': return copy.deepcopy(self.products)
        if path == 'objects/chores': return copy.deepcopy(self.chores)
        if path == 'objects/quantity_unit_conversions_resolved': return []
        return copy.deepcopy(self.rows[path.removeprefix('objects/')])

    def preview(self): return merge.merge_preview(1, 2)
    def combine(self, token): return merge.merge_products(1, 2, self.source['name'], self.target['name'], token)
    def assert_no_write(self): self.assertTrue(all(call.args[0] == 'GET' for call in self.http.call_args_list))


class MergeAuditTests(MergeFixture, unittest.TestCase):
    def test_nonzero_stock_and_history_are_supported_by_one_native_transaction(self):
        preview = self.preview()
        self.assertTrue(preview['can_merge'], preview)
        self.assertEqual(preview['source']['stock_amount'], '2')
        self.assert_no_write()
        self.combine(preview['token'])
        self.assertEqual(sum(row['amount'] for row in self.rows['stock']), 5)
        self.assertEqual(self.rows['stock_log'][0]['note'], 'keep history')
        self.assertEqual(self.rows['stock_log'][0]['id'], 20)
        self.assertEqual([call.args for call in self.http.call_args_list if call.args[0] != 'GET'], [('POST', 'stock/products/2/merge/1')])

    def test_changed_stock_name_barcode_and_reference_reject_stale_preview(self):
        for collection in ('stock', 'stock_log', 'product_barcodes', 'shopping_list'):
            with self.subTest(collection=collection):
                token = self.preview()['token']
                self.rows[collection].append({'id': 500, 'product_id': 1, 'amount': 1, 'barcode': '8411111111111'})
                with self.assertRaises(barcode_stock.BarcodeError): self.combine(token)
                self.rows[collection].pop()
        token = self.preview()['token']; self.target['name'] = 'Renamed'
        with self.assertRaises(barcode_stock.BarcodeError): self.combine(token)
        self.assert_no_write()

    def test_units_incompatible_conversions_hierarchy_and_tare_block(self):
        for field, value in [('qu_id_stock', 3), ('qu_id_purchase', 3), ('enable_tare_weight_handling', 1), ('parent_product_id', 3)]:
            old = self.source.get(field); self.source[field] = value
            self.assertFalse(self.preview()['can_merge'])
            if old is None: self.source.pop(field, None)
            else: self.source[field] = old
        self.rows['quantity_unit_conversions'].append({'id': 41, 'product_id': 2, 'from_qu_id': 2, 'to_qu_id': 2, 'factor': 5})
        self.assertFalse(self.preview()['can_merge'])
        self.assert_no_write()

    def test_unverified_version_archives_custom_fields_and_source_local_links_block(self):
        self.version = '4.8.0'; self.assertFalse(self.preview()['can_merge']); self.version = '4.7.1'
        self.source['active'] = 0; self.assertFalse(self.preview()['can_merge']); self.source['active'] = 1
        self.source['userfields'] = {'private': 'retained'}; self.assertFalse(self.preview()['can_merge']); self.source['userfields'] = None
        self.local_guard.return_value = ['historial de tickets']
        self.assertFalse(self.preview()['can_merge'])
        self.local_guard.assert_called_with(1)
        self.assert_no_write()

    def test_missing_reference_data_and_same_product_never_dispatch(self):
        self.rows['stock_log'] = None
        with self.assertRaises(ValueError): self.preview()
        with self.assertRaises(barcode_stock.BarcodeError): merge.merge_preview(1, 1)
        self.assert_no_write()

    def test_both_default_shopping_rows_need_review_before_creating_canonical_collision(self):
        self.rows['shopping_list'] = [{'id': 60, 'product_id': 1, 'shopping_list_id': 1}, {'id': 61, 'product_id': 2, 'shopping_list_id': 1}]
        self.assertFalse(self.preview()['can_merge'])
        self.assert_no_write()

    def test_post_write_history_verification_detects_missing_or_changed_data(self):
        token = self.preview()['token']; self.corrupt = True
        with self.assertRaises(RuntimeError): self.combine(token)
        self.assertEqual(sum(call.args[0] == 'POST' for call in self.http.call_args_list), 1)


class MergeApiTests(MergeFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        for mock in (patch.object(web, 'INGRESS_MODE', True), patch.dict(web.app.config, SECRET_KEY='merge-test-key')):
            mock.start(); self.addCleanup(mock.stop)
        self.client = web.app.test_client()
        self.headers = {'X-CSRF-Token': self.client.get('/api/v1/auth/status').json['csrf_token']}

    def payload(self):
        response = self.client.get('/api/v1/catalog/merge-preview?source_id=1&target_id=2')
        self.assertEqual(response.status_code, 200, response.json)
        return {'source_id': 1, 'target_id': 2, 'expected_source': self.source['name'], 'expected_target': self.target['name'], 'confirmation': self.target['name'], 'token': response.json['token'], 'operation_id': str(uuid.uuid4())}

    def test_auth_csrf_and_exact_name_precede_one_recorded_dispatch(self):
        with patch.object(web, 'INGRESS_MODE', False):
            self.assertEqual(self.client.get('/api/v1/catalog/merge-preview?source_id=1&target_id=2').status_code, 401)
        self.assertEqual(self.client.post('/api/v1/catalog/products/merge', json={}).status_code, 403)
        payload = self.payload(); payload['confirmation'] = 'wrong'
        self.assertEqual(self.client.post('/api/v1/catalog/products/merge', json=payload, headers=self.headers).status_code, 400)
        self.assert_no_write()
        payload['confirmation'] = self.target['name']
        for _ in range(2):
            response = self.client.post('/api/v1/catalog/products/merge', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(sum(call.args[0] == 'POST' for call in self.http.call_args_list), 1)

    def test_uncertain_native_merge_is_not_replayed_or_exposed(self):
        payload = self.payload(); self.uncertain = True
        for status in (502, 409):
            response = self.client.post('/api/v1/catalog/products/merge', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, status, response.json)
            self.assertNotIn('private upstream', response.get_data(as_text=True))
        self.assertEqual(sum(call.args[0] == 'POST' for call in self.http.call_args_list), 1)
