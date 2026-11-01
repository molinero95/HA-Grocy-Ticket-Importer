"""Regression tests for the isolated receipt API and durable one-shot import guard."""
import hashlib
import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

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
        self.importer.assert_called_once_with(self.rid, "--commit")

    def test_failed_import_remains_blocked_until_manual_reconciliation(self):
        self.importer.return_value = SimpleNamespace(returncode=1, stdout="", stderr="failure")
        self.authorize()
        first = self.client.post("/api/v1/receipts/" + self.rid + "/commit")
        self.assertEqual(first.status_code, 502)
        self.authorize()
        second = self.client.post("/api/v1/receipts/" + self.rid + "/commit")
        self.assertEqual(second.status_code, 409)
        self.importer.assert_called_once()

    def test_preview_rejects_changed_ticket_quantity(self):
        self.authorize()
        response = self.client.post("/api/v1/receipts/" + self.rid + "/preview", json={"items": [{"name": "Arroz", "purchase_units": "2", "pieces_per_pack": 1}]})
        self.assertEqual(response.status_code, 400)
        self.importer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
