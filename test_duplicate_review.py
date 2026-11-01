"""Differences persist per pair, work for three-way groups and can be undone."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import barcode_stock
import duplicate_review as review
import duplicate_candidates
import variant_catalog
with patch.dict(os.environ, WEB_PASSWORD='test-password', WEB_SESSION_SECRET='test-secret-key'):
    import web


class DifferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.products = [{'id': pid, 'name': 'Leche entera', 'active': 1} for pid in (1, 2, 3)]
        for mock in (patch.object(variant_catalog, 'CATALOG_DB', self.root / 'existing.sqlite3'),
                     patch.object(web, 'INGRESS_MODE', True), patch.dict(web.app.config, SECRET_KEY='review-key'),
                     patch.dict(os.environ, WEB_PASSWORD='test-password'),
                     patch.object(barcode_stock, 'grocy', side_effect=self.grocy)):
            result = mock.start(); self.addCleanup(mock.stop)
            if getattr(mock, 'attribute', None) == 'grocy': self.http = result
        self.client = web.app.test_client()
        self.headers = {'X-CSRF-Token': self.client.get('/api/v1/auth/status').json['csrf_token']}

    def grocy(self, method, path, *_):
        self.assertEqual(method, 'GET')
        if path == 'objects/product_barcodes': return []
        if path == 'objects/products': return copy.deepcopy(self.products)
        return copy.deepcopy(next(p for p in self.products if p['id'] == int(path.rsplit('/', 1)[1])))

    def pairs(self):
        return {tuple(item['id'] for item in group['items']) for group in duplicate_candidates.detect_duplicates()}

    def test_marking_one_pair_does_not_hide_other_pairs_and_survives_reopening(self):
        self.assertEqual(self.pairs(), {(1, 2), (1, 3), (2, 3)})
        review.set_different(self.products[1], self.products[0])
        self.assertEqual(self.pairs(), {(1, 3), (2, 3)})
        self.assertEqual(len(review.differences()), 1)
        review.set_different(self.products[0], self.products[1])
        self.assertEqual(len(review.differences()), 1)
        review.undo_difference(2, 1)
        self.assertEqual(self.pairs(), {(1, 2), (1, 3), (2, 3)})

    def test_saved_decision_survives_a_rename_and_archives_are_excluded(self):
        review.set_different(self.products[0], self.products[1])
        for product in self.products: product['name'] = 'Leche de pruebas'
        self.assertNotIn((1, 2), self.pairs())
        self.products[2]['active'] = 0
        self.assertEqual(self.pairs(), set())

    def test_api_auth_csrf_stale_names_and_undo_do_not_mutate_grocy(self):
        payload = {'left_id': 1, 'right_id': 2, 'left_name': 'Leche entera', 'right_name': 'Leche entera'}
        url = '/api/v1/catalog/duplicates/differences'
        with patch.object(web, 'INGRESS_MODE', False):
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.put(url, json=payload).status_code, 403)
        self.assertEqual(self.client.delete(url + '/1/2').status_code, 403)
        stale = self.client.put(url, json={**payload, 'left_name': 'old'}, headers=self.headers)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(review.differences(), [])
        for _ in range(2): self.assertEqual(self.client.put(url, json=payload, headers=self.headers).status_code, 200)
        self.assertNotIn((1, 2), self.pairs())
        self.assertEqual(len(self.client.get(url).json['differences']), 1)
        self.assertEqual(self.client.delete(url + '/2/1', headers=self.headers).status_code, 200)
        self.assertIn((1, 2), self.pairs())
        self.assertTrue(all(call.args[0] == 'GET' for call in self.http.call_args_list))

    def test_corrupt_decision_database_fails_instead_of_silently_repeating_suggestions(self):
        variant_catalog.CATALOG_DB.write_bytes(b'not sqlite')
        self.assertEqual(self.client.get('/api/v1/catalog/duplicates').status_code, 503)
        self.assertEqual(self.client.get('/api/v1/catalog/duplicates/differences').status_code, 503)
