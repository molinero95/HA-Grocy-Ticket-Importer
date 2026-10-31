"""Web UI tests; never call OpenAI or Grocy."""
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

with patch.dict(os.environ, {"WEB_PASSWORD": "test-password", "WEB_SESSION_SECRET": "test-secret-key"}, clear=False):
    import web

class WebTests(unittest.TestCase):
    def setUp(self):
        # Keep credentials active throughout each test, not just during module import.
        env_patch = patch.dict(os.environ, {"WEB_PASSWORD": "test-password",
                                           "WEB_SESSION_SECRET": "test-secret-key",
                                           "HA_INGRESS_MODE": "0"})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patcher = patch.object(web, "DATA", Path(self.temp.name))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        web.app.config["TESTING"] = True
        self.client = web.app.test_client()

    def csrf(self):
        self.client.get("/")
        with self.client.session_transaction() as session:
            return session["csrf"]

    def login(self):
        token = self.csrf()
        r = self.client.post("/login", data={"password": "test-password", "csrf": token})
        self.assertEqual(r.status_code, 302)
        return self.csrf()

    def test_configuration_needed(self):
        with patch.dict(os.environ, {"WEB_PASSWORD": ""}):
            self.assertEqual(self.client.get("/").status_code, 503)

    def test_login_csrf_required(self):
        self.assertEqual(self.client.post("/login", data={"password": "test-password"}).status_code, 403)

    def test_login_wrong_password(self):
        self.assertEqual(self.client.post("/login", data={"csrf": self.csrf(), "password": "wrong"}).status_code, 401)

    def test_requires_login_for_upload(self):
        self.assertEqual(self.client.post("/upload", data={"csrf": self.csrf()}).status_code, 401)

    def test_product_association_uses_searchable_list(self):
        with patch.object(web.barcode_stock, "list_products", return_value=[
                {"id": 12, "name": "Nutella 350 g"},
                {"id": 14, "name": "Leche Asturiana"}]):
            self.login()
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="product-search"', response.data)
        self.assertIn(b'data-product-id="12"', response.data)
        self.assertIn(b'Nutella 350 g', response.data)
        self.assertIn(b'id="selected-product-id"', response.data)
        self.assertNotIn(b'<select name="product_id"', response.data)

    def test_camera_scanner_available_for_all_barcode_actions(self):
        self.login()
        with patch.object(web.barcode_stock, "list_products", return_value=[]):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'class="scan-trigger"'), 4)
        self.assertIn(b'id="scanner-dialog"', response.data)
        self.assertIn(b'new BarcodeDetector', response.data)
        self.assertIn(b'getUserMedia', response.data)
        self.assertIn(b'input[name="barcode"]', response.data)
        self.assertIn(b'No se a', response.data)
        self.assertIn(b'id="scanner-stop"', response.data)

    def test_invalid_file_type_blocked(self):
        token = self.login()
        r = self.client.post("/upload", data={"csrf": token,
                         "ticket": (io.BytesIO(b"bad"), "malware.exe")},
                         content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    @patch.object(web.extract, "extract")
    def test_upload_then_preview_requires_explicit_commit(self, mock_extract):
        mock_extract.return_value = {"merchant": "Test", "receipt_date": "2026-09-28",
            "total": 1.0, "items": [{"name": "Milk", "quantity": 1,
            "unit_price": 1.0, "ambiguous": False, "reason": ""}],
            "source_sha256": "ab" * 32}
        token = self.login()
        r = self.client.post("/upload", data={"csrf": token,
                         "ticket": (io.BytesIO(b"%PDF-1.4"), "receipt.pdf")},
                         content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"1 l\xc3\xadneas", r.data)
        self.assertIn(b"Milk", r.data)
        mock_extract.assert_called_once()
        with self.client.session_transaction() as session:
            rid = session["receipt_id"]
        self.assertEqual(self.client.post("/commit/" + rid, data={"csrf": token}).status_code, 403)
        with patch.object(web, "run_import", return_value=Mock(returncode=0, stdout="WOULD IMPORT", stderr="")) as run:
            self.assertEqual(self.client.post("/preview/" + rid, data={"csrf": token}).status_code, 200)
            run.assert_called_once_with(rid, "--dry-run")
        with patch.object(web, "run_import", return_value=Mock(returncode=0, stdout="IMPORTED", stderr="")) as run:
            self.assertEqual(self.client.post("/commit/" + rid, data={"csrf": token}).status_code, 200)
            run.assert_called_once_with(rid, "--commit")
            self.assertEqual(self.client.post("/commit/" + rid, data={"csrf": token}).status_code, 403)

if __name__ == "__main__":
    unittest.main()
