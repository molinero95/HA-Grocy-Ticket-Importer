"""Absolute quantity edits preserve identities and at-most-once stock semantics."""
import copy
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch
import barcode_stock
with patch.dict(os.environ, WEB_PASSWORD='test-password', WEB_SESSION_SECRET='test-secret-key'):
    import web


class QuantityTests(unittest.TestCase):
    def setUp(self):
        self.row = {'id': 4, 'product_id': 7, 'shopping_list_id': 1, 'amount': 0.1, 'done': 0, 'note': 'Conservar nota', 'qu_id': 2}
        self.calls = []
        self.lost = False
        self.dir = tempfile.TemporaryDirectory(); self.addCleanup(self.dir.cleanup)
        for mock in (patch.object(web, 'INGRESS_MODE', True), patch.dict(web.app.config, SECRET_KEY='quantity-session'), patch.dict(os.environ, STOCK_COMMAND_DB=self.dir.name+'/commands.sqlite3'), patch.object(barcode_stock, 'grocy', side_effect=self.grocy)):
            mock.start(); self.addCleanup(mock.stop)
        self.client = web.app.test_client()
        self.headers = {'X-CSRF-Token': self.client.get('/api/v1/auth/status').json['csrf_token']}

    def grocy(self, method, path, body=None):
        self.calls.append((method, path, body))
        self.assertEqual(path, 'objects/shopping_list/4')
        if method == 'PUT':
            self.row.update(body)
            if self.lost: raise ConnectionError('private provider details')
        return copy.deepcopy(self.row)

    def payload(self):
        return {'amount': '2.75', 'expected_amount': '0.1', 'product_id': 7, 'expected_done': False, 'operation_id': str(uuid.uuid4())}

    def test_absolute_update_is_one_put_preserving_note_done_product_and_unit(self):
        original = dict(self.row)
        payload = self.payload()
        for _ in range(2):
            result = self.client.put('/api/v1/shopping/4/quantity', json=payload, headers=self.headers)
            self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(self.row, {**original, 'amount': 2.75})
        self.assertEqual(sum(call[0] == 'PUT' for call in self.calls), 1)
        self.assertEqual(len(self.calls), 3)

    def test_stale_rows_other_lists_invalid_amounts_and_csrf_never_write(self):
        self.assertEqual(self.client.put('/api/v1/shopping/4/quantity', json=self.payload()).status_code, 403)
        for change in ({'amount': '0'}, {'amount': 'NaN'}, {'amount': '1.123'}, {'expected_amount': '2'}, {'product_id': 8}, {'expected_done': True}):
            result = self.client.put('/api/v1/shopping/4/quantity', json={**self.payload(), **change}, headers=self.headers)
            self.assertEqual(result.status_code, 409, result.json)
        self.row['shopping_list_id'] = 2
        self.assertEqual(self.client.put('/api/v1/shopping/4/quantity', json=self.payload(), headers=self.headers).status_code, 409)
        self.assertFalse(any(call[0] == 'PUT' for call in self.calls))

    def test_uncertain_quantity_and_stock_commands_are_never_replayed(self):
        self.lost = True
        payload = self.payload()
        for status in (502, 409):
            self.assertEqual(self.client.put('/api/v1/shopping/4/quantity', json=payload, headers=self.headers).status_code, status)
        self.assertEqual(sum(call[0] == 'PUT' for call in self.calls), 1)
        payload = {'desired_amount': '2.123', 'expected_amount': '1.123', 'step': True, 'operation_id': str(uuid.uuid4())}
        with patch.object(barcode_stock, 'prepare_stock_adjustment', return_value={'after': '2.123'}) as prepare, patch.object(barcode_stock, 'apply_stock_adjustment', side_effect=ConnectionError('uncertain')) as apply:
            for status in (502, 409):
                self.assertEqual(self.client.post('/api/v1/catalog/products/7/stock', json=payload, headers=self.headers).status_code, status)
            prepare.assert_called_once_with(7, '2.123', '1.123', 3)
            apply.assert_called_once()
