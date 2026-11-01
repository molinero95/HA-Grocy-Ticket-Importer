"""Regression tests for the isolated receipt API and durable one-shot import guard."""
import hashlib
import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask
from api_receipts import register_receipt_routes


class ReceiptSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data = Path(self.directory.name)
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"
        self.importer = Mock(return_value=SimpleNamespace(returncode=0, stdout="OK", stderr=""))
        register_receipt_routes(self.app, self.data, {".pdf"}, Mock(), self.importer, threading.Lock())
        self.client = self.app.test_client()
        self.rid = "a" * 32
        self.path = self.data / (self.rid + ".json")
        self.path.write_text(json.dumps({"items": [{"name": "Arroz", "quantity": 1}]}), encoding="utf-8")

    def authorize(self, digest=None):
        with self.client.session_transaction() as session:
            session["receipt_id"] = self.rid
            session["previewed"] = self.rid
            session["previewed_digest"] = digest or hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_changed_receipt_requires_new_preview(self):
        self.authorize()
        self.path.write_text(json.dumps({"items": [{"name": "Leche", "quantity": 1}]}), encoding="utf-8")
        response = self.client.post("/api/v1/receipts/" + self.rid + "/commit")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"], "receipt_changed_since_preview")
        self.importer.assert_not_called()

    def test_double_commit_runs_importer_only_once(self):
        self.authorize()
        first = self.client.post("/api/v1/receipts/" + self.rid + "/commit")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json["status"], "committed")
        self.assertTrue((self.data / (self.rid + ".commit-started")).exists())
        self.authorize()
        second = self.client.post("/api/v1/receipts/" + self.rid + "/commit")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json["error"], "receipt_already_submitted")
        self.assertEqual([call.args for call in self.importer.call_args_list], [(self.rid, "--dry-run"), (self.rid, "--commit")])

    def test_failed_import_remains_blocked_until_manual_reconciliation(self):
        self.importer.side_effect = [SimpleNamespace(returncode=0, stdout="OK", stderr=""), SimpleNamespace(returncode=1, stdout="", stderr="failure")]
        self.authorize()
        first = self.client.post("/api/v1/receipts/" + self.rid + "/commit")
        self.assertEqual(first.status_code, 502)
        self.authorize()
        second = self.client.post("/api/v1/receipts/" + self.rid + "/commit")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(self.importer.call_count, 2)

    def test_preview_accepts_corrected_stock_quantity_and_preserves_receipt_cost(self):
        self.authorize()
        response = self.client.post("/api/v1/receipts/" + self.rid + "/preview", json={"items": [{"name": "Arroz", "purchase_units": "2", "pieces_per_pack": 1}]})
        self.assertEqual(response.status_code, 200)
        saved = json.loads(self.path.read_text())["items"][0]
        self.assertEqual(saved["quantity"], 1)
        self.assertEqual(saved["purchase_units"], "2")
        self.importer.assert_called_once_with(self.rid, "--dry-run")

    def test_review_lines_never_authorize_partial_commit(self):
        self.authorize()
        self.importer.return_value = SimpleNamespace(returncode=0, stdout="[1] REVIEW Arroz: ambiguous", stderr="")
        preview = self.client.post('/api/v1/receipts/' + self.rid + '/preview', json={'items': [{'name': 'Arroz'}]})
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(preview.json['ready_to_commit'])
        self.assertEqual(self.client.post('/api/v1/receipts/' + self.rid + '/commit').status_code, 403)

    def test_catalog_change_before_commit_requires_new_simulation(self):
        self.authorize()
        self.importer.return_value = SimpleNamespace(returncode=0, stdout="[1] REVIEW Arroz: archived", stderr="")
        result = self.client.post('/api/v1/receipts/' + self.rid + '/commit')
        self.assertEqual(result.status_code, 409)
        self.assertFalse((self.data / (self.rid + '.commit-started')).exists())
        self.importer.assert_called_once_with(self.rid, '--dry-run')

    def test_rejected_preview_preserves_original_text_and_invalidates_old_preview(self):
        self.authorize()
        response = self.client.post('/api/v1/receipts/' + self.rid + '/preview', json={'items': [{'name': 'Canonical', 'purchase_units': 'NaN'}]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(self.path.read_text())['items'][0]['name'], 'Arroz')
        self.assertEqual(self.client.post('/api/v1/receipts/' + self.rid + '/commit').status_code, 403)

    def test_original_name_cannot_be_replaced_by_client_or_later_edits(self):
        self.authorize()
        for name in ('Arroz largo', 'Arroz basmati'):
            response = self.client.post('/api/v1/receipts/' + self.rid + '/preview', json={'items': [{'name': name, 'original_name': 'forged'}]})
            self.assertEqual(response.status_code, 200)
        item = json.loads(self.path.read_text())['items'][0]
        self.assertEqual(item['original_name'], 'Arroz')
        self.assertEqual(item['name'], 'Arroz basmati')

    def test_preview_plan_identity_changes_require_resimulation(self):
        self.authorize()
        self.importer.return_value = SimpleNamespace(returncode=0, stdout='[1] WOULD IMPORT Arroz (existing id=1)', stderr='')
        self.assertEqual(self.client.post('/api/v1/receipts/' + self.rid + '/preview', json={'items': [{'name': 'Arroz'}]}).status_code, 200)
        self.importer.return_value = SimpleNamespace(returncode=0, stdout='[1] WOULD IMPORT Arroz (existing id=2)', stderr='')
        self.assertEqual(self.client.post('/api/v1/receipts/' + self.rid + '/commit').status_code, 409)
        self.assertFalse((self.data / (self.rid + '.commit-started')).exists())

    def test_review_context_requires_session_and_marks_changed_mappings_stale(self):
        url = '/api/v1/receipts/' + self.rid + '/review-context'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.authorize()
        reads = {'objects/products': [{'id': 17, 'name': 'Arroz largo', 'qu_id_stock': 2}],
                 'objects/quantity_units': [{'id': 2, 'name': 'Piece'}], 'objects/quantity_unit_conversions': []}
        with patch('api_receipts.importer.grocy', side_effect=lambda method, route: reads[route]) as remote, patch('api_receipts.mappings', return_value={'arroz': {'product_id': 17, 'stock_unit': 'kg', 'pieces_per_pack': 1}}):
            result = self.client.get(url)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertTrue(result.json['mappings']['arroz']['stale'])
        self.assertTrue(result.json['line_mappings'][0]['stale'])
        self.assertTrue(all(call.args[0] == 'GET' for call in remote.call_args_list))


if __name__ == "__main__":
    unittest.main()
