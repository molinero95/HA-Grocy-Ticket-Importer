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
