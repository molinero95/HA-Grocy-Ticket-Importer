"""Visual thresholds persist without Grocy stock/minimum/shopping writes."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import stock_thresholds as thresholds
import variant_catalog
with patch.dict(os.environ, WEB_PASSWORD='test-password', WEB_SESSION_SECRET='test-secret-key'):
    import web


class ThresholdTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'catalog.sqlite3'
        for mock in (patch.object(variant_catalog, 'CATALOG_DB', self.path), patch.object(web, 'INGRESS_MODE', True), patch.dict(web.app.config, SECRET_KEY='threshold-key')):
            mock.start(); self.addCleanup(mock.stop)
        self.client = web.app.test_client()
        self.headers = {'X-CSRF-Token': self.client.get('/api/v1/auth/status').json['csrf_token']}

    def test_default_zero_and_persistent_per_product_decimal_values(self):
        self.assertEqual(thresholds.thresholds().get(7, '0'), '0')
        self.assertEqual(thresholds.save_threshold(7, '2.50', '0'), '2.5')
        self.assertEqual(thresholds.thresholds(), {7: '2.5'})
        thresholds.save_threshold(8, '0.1', '0')
        self.assertEqual(thresholds.thresholds(), {7: '2.5', 8: '0.1'})
        self.assertEqual(thresholds.save_threshold(7, '2.5', '0'), '2.5')

    def test_invalid_or_stale_values_cannot_overwrite_a_saved_threshold(self):
        thresholds.save_threshold(7, '3', '0')
        for value in ('-1', 'NaN', 'Infinity', '0.001', '1000000', ''):
            with self.assertRaises(ValueError): thresholds.save_threshold(7, value, '3')
        with self.assertRaisesRegex(ValueError, 'ha cambiado'): thresholds.save_threshold(7, '2', '0')
        self.assertEqual(thresholds.thresholds()[7], '3')

    def test_api_requires_csrf_and_only_reads_grocy_without_changing_stock_or_shopping(self):
        url = '/api/v1/catalog/products/7/stock-threshold'
        payload = {'amount': '2', 'expected': '0'}
        with patch.object(web.barcode_stock, 'grocy', return_value={'id': 7}) as grocy:
            self.assertEqual(self.client.put(url, json=payload).status_code, 403)
            grocy.assert_not_called()
            self.assertEqual(self.client.put(url, json=payload, headers=self.headers).status_code, 200)
            grocy.assert_called_once_with('GET', 'objects/products/7')
        self.assertEqual(thresholds.thresholds(), {7: '2'})

    def test_inventory_and_product_apis_return_current_thresholds_with_zero_fallback(self):
        thresholds.save_threshold(7, '4', '0')
        with patch.object(web.barcode_stock, 'inventory_with_shopping', return_value=[{'id': 7}, {'id': 8}]), patch('api_photos.local_image_url', return_value=None):
            response = self.client.get('/api/v1/inventory')
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual([row['stock_threshold'] for row in response.json['items']], ['4', '0'])
        with patch.object(web.barcode_stock, 'product_detail', return_value={'id': 7}), patch('api_photos.local_image_url', return_value=None):
            self.assertEqual(self.client.get('/api/v1/catalog/products/7').json['stock_threshold'], '4')

    def test_warning_opt_out_persists_independently_and_stale_clients_cannot_enable_it(self):
        thresholds.save_threshold(7, '3', '0')
        thresholds.save_threshold(7, '3', '3', False, True)
        self.assertEqual(thresholds.settings()[7], {'amount': '3', 'warning_enabled': False})
        with self.assertRaises(ValueError): thresholds.save_threshold(7, '4', '3', True, True)
        thresholds.save_threshold(7, '3', '3', True, False)
        self.assertTrue(thresholds.settings()[7]['warning_enabled'])
