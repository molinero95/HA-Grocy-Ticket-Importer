"""Read-only final plans, strict guards and at-most-once partial merge dispatch."""
import copy
import unittest
import uuid
from decimal import Decimal
from unittest.mock import patch
import merge_resolution as resolved
import barcode_stock
import test_merge_audit as baseline
from test_merge_audit import MergeFixture, web


class MergeResolutionTests(MergeFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.rows['quantity_units'] = [{'id': 2, 'name': 'Piece'}, {'id': 3, 'name': 'Kilogram'}, {'id': 4, 'name': 'Pack'}]
        self.source.update(qu_id_stock=3, qu_id_purchase=3, qu_id_consume=3, qu_id_price=3)
        self.spec = dict(final_name=self.target['name'], unit_id=2, purchase_unit_id=2, pack_size='1', source_factor='2', target_factor='1', final_stock='8')
        guard = patch.object(resolved, '_local_deletion_blockers', return_value=[]);guard.start();self.addCleanup(guard.stop)
        threshold = patch.object(resolved, 'threshold', return_value={'amount': '2', 'warning_enabled': False});threshold.start();self.addCleanup(threshold.stop)

    def test_preview_converts_sum_and_explicit_correction_without_writes(self):
        review = resolved.review(1, 2, self.spec)
        self.assertTrue(review['can_merge'], review)
        self.assertEqual(review['combined_stock'], '7')
        self.assertEqual(review['stock_correction'], '1')
        self.assertEqual(review['resolution']['threshold_amount'], '2')
        self.assert_no_write()

    def test_bad_amounts_units_names_and_factors_never_write(self):
        for patch in ({'source_factor': 'NaN'}, {'source_factor': '0'}, {'target_factor': '2'}, {'final_stock': '-1'}, {'final_stock': '1.123'}, {'unit_id': 4}, {'purchase_unit_id': True}, {'pack_size': '1.5'}, {'final_name': ''}):
            with self.subTest(patch=patch), self.assertRaises(ValueError): resolved.review(1, 2, {**self.spec, **patch})
        self.assert_no_write()

    def test_source_receipt_links_and_other_hard_blockers_remain(self):
        self.local_guard.return_value = ['historial de tickets']
        review = resolved.review(1, 2, self.spec)
        self.assertFalse(review['can_merge'])
        with self.assertRaises(barcode_stock.BarcodeError): resolved.commit(1, 2, self.source['name'], self.target['name'], self.spec, review['token'])
        self.assert_no_write()

    def test_stock_threshold_units_and_plan_changes_invalidate_token(self):
        for change in ('stock', 'units', 'spec'):
            review = resolved.review(1, 2, self.spec)
            if change == 'stock': self.rows['stock'][0]['amount'] += 1
            if change == 'units': self.rows['quantity_units'][0]['name'] = 'Unidades'
            spec = {**self.spec, 'final_stock': '9'} if change == 'spec' else self.spec
            with self.assertRaises(barcode_stock.BarcodeError): resolved.commit(1, 2, self.source['name'], self.target['name'], spec, review['token'])
        self.assert_no_write()

    def test_target_threshold_conversion_is_explicit_and_preserves_optout(self):
        self.spec.update(unit_id=3, purchase_unit_id=3, source_factor='1', target_factor='.5', final_stock='3.5')
        review = resolved.review(1, 2, self.spec)
        self.assertEqual(review['resolution']['threshold_amount'], '1')
        self.assertEqual(resolved.options(1, 2)['target_threshold']['warning_enabled'], False)
        self.assert_no_write()

    def test_normalization_loss_stops_before_merge(self):
        data = resolved.snapshot(1, 2);after = copy.deepcopy(data)
        with self.assertRaises(RuntimeError): resolved._verify_normalization(data, after, 1, Decimal(2))
        self.assert_no_write()


class ResolvedMergeApiTests(MergeFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        for mock in (patch.object(web, 'INGRESS_MODE', True), patch.dict(web.app.config, SECRET_KEY='merge-test-key')):
            mock.start(); self.addCleanup(mock.stop)
        self.client = web.app.test_client()
        self.headers = {'X-CSRF-Token': self.client.get('/api/v1/auth/status').json['csrf_token']}
    def test_resolved_csrf_and_auth(self):
        self.assertEqual(self.client.post('/api/v1/catalog/merge-resolution-preview', json={}).status_code, 403)
        with patch.object(web, 'INGRESS_MODE', False):
            self.assertEqual(self.client.get('/api/v1/catalog/merge-resolution?source_id=1&target_id=2').status_code, 401)

    def test_partial_stage_is_not_replayed_and_hides_remote_error(self):
        payload = {'source_id': 1, 'target_id': 2, 'expected_source': self.source['name'], 'expected_target': self.target['name'], 'resolution': {'final_name': self.target['name']}, 'confirmation': self.target['name'], 'token': 'a'*64, 'operation_id': str(uuid.uuid4())}
        with patch.object(resolved, 'commit', side_effect=resolved.PartialMerge('ajustar_stock_final')) as execute:
            response = self.client.post('/api/v1/catalog/products/merge-resolved', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json['stage'], 'ajustar_stock_final')
            self.assertEqual(self.client.post('/api/v1/catalog/products/merge-resolved', json=payload, headers=self.headers).status_code, 409)
            execute.assert_called_once()
