"""Photo/auth contracts against Flask; no real Grocy or public image requests."""
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
with patch.dict(os.environ, {"WEB_PASSWORD": "test-password", "WEB_SESSION_SECRET": "test-secret-key"}):
    import web

CODE = "8412345678901"
URL = "https://images.openfoodfacts.org/images/products/test.jpg"


class PhotoApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"WEB_PASSWORD": "test-password", "PRODUCT_IMAGE_DIR": self.temp.name})
        env.start()
        self.addCleanup(env.stop)
        ingress = patch.object(web, "INGRESS_MODE", True)
        ingress.start()
        self.addCleanup(ingress.stop)
        self.client = web.app.test_client()
        self.token = self.client.get("/api/v1/auth/status").json["csrf_token"]
        self.headers = {"X-CSRF-Token": self.token}
        self.product = {"id": 7, "name": "Producto", "barcodes": [CODE], "image_url": None}

    def test_discovery_is_read_only_and_exact_code(self):
        with patch("product_images.lookup_image", return_value={"barcode": CODE, "image_url": URL}) as lookup, patch.object(web.barcode_stock, "grocy") as grocy:
            response = self.client.get("/api/v1/photos/" + CODE)
        self.assertEqual(response.status_code, 200)
        lookup.assert_called_once_with(CODE)
        grocy.assert_not_called()

    def test_photo_save_requires_csrf(self):
        with patch("product_images.lookup_image") as lookup:
            response = self.client.post("/api/v1/catalog/products/7/photo-lookup", json={"barcode": CODE})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.is_json)
        lookup.assert_not_called()

    def test_photo_save_rejects_unassociated_code_before_lookup(self):
        with patch.object(web.barcode_stock, "product_detail", return_value=self.product), patch("product_images.lookup_image") as lookup, patch.object(web.barcode_stock, "save_product_photo") as save:
            response = self.client.post("/api/v1/catalog/products/7/photo-lookup", json={"barcode": "12345678", "image_url": URL}, headers=self.headers)
        self.assertEqual(response.status_code, 409)
        lookup.assert_not_called()
        save.assert_not_called()

    def test_photo_save_uses_server_result_and_never_a_client_url(self):
        with patch.object(web.barcode_stock, "product_detail", return_value=self.product), patch("product_images.lookup_image", return_value={"image_url": URL}), patch.object(web.barcode_stock, "save_product_photo") as save:
            response = self.client.post("/api/v1/catalog/products/7/photo-lookup", json={"barcode": CODE, "image_url": "http://internal/secret"}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        save.assert_called_once_with(7, URL)

    def test_missing_or_untrusted_photo_does_not_change_metadata(self):
        for found in (None, {"image_url": None}, {"image_url": "https://evil.invalid/a.jpg"}):
            with self.subTest(found=found), patch.object(web.barcode_stock, "product_detail", return_value=self.product), patch("product_images.lookup_image", return_value=found), patch.object(web.barcode_stock, "save_product_photo") as save:
                response = self.client.post("/api/v1/catalog/products/7/photo-lookup", json={"barcode": CODE}, headers=self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json["saved"])
                save.assert_not_called()

    def test_automatic_lookup_preserves_existing_photo(self):
        for local in (False, True):
            if local:
                Path(self.temp.name, "7.jpg").write_bytes(b"existing-photo")
            with self.subTest(local=local), patch.object(web.barcode_stock, "product_detail", return_value={**self.product, "image_url": URL}), patch("product_images.lookup_image") as lookup:
                response = self.client.post("/api/v1/catalog/products/7/photo-lookup", json={"barcode": CODE}, headers=self.headers)
                self.assertTrue(response.json["preserved"])
                lookup.assert_not_called()

    def test_local_upload_is_sanitized_and_shown_in_all_views(self):
        data = io.BytesIO()
        Image.new("RGBA", (20, 10), "red").save(data, format="PNG")
        data.seek(0)
        with patch.object(web.barcode_stock, "product_detail", return_value=self.product):
            response = self.client.post("/api/v1/catalog/products/7/photo", data={"photo": (data, "arbitrary.png")}, headers=self.headers)
            detail = self.client.get("/api/v1/catalog/products/7")
        self.assertEqual(response.status_code, 200)
        url = response.json["photo_url"]
        self.assertIn("?v=", url)
        with Image.open(Path(self.temp.name, "7.jpg")) as saved:
            self.assertEqual(saved.format, "JPEG")
            self.assertEqual(saved.mode, "RGB")
            self.assertEqual(saved.getexif(), {})
        with patch.object(web.barcode_stock, "inventory_with_shopping", return_value=[{"id": 7}]), patch.object(web.barcode_stock, "shopping_list_snapshot", return_value=[{"id": 9, "product_id": 7}]), patch.object(web.shopping_match_queue, "pending", return_value=[]):
            inventory = self.client.get("/api/v1/inventory")
            shopping = self.client.get("/api/v1/shopping")
        self.assertEqual(detail.json["image_url"], url)
        self.assertEqual(inventory.json["items"][0]["image_url"], url)
        self.assertEqual(shopping.json["items"][0]["image_url"], url)
        self.assertEqual(self.client.get("/" + url).status_code, 200)
        self.assertFalse(Path(self.temp.name, "7.tmp").exists())

    def test_invalid_upload_preserves_previous_file(self):
        previous = Path(self.temp.name, "7.jpg")
        previous.write_bytes(b"previous")
        with patch.object(web.barcode_stock, "product_detail", return_value=self.product):
            response = self.client.post("/api/v1/catalog/products/7/photo", data={"photo": (io.BytesIO(b"<script>"), "fake.jpg")}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(previous.read_bytes(), b"previous")

    def test_oversized_photo_is_rejected_before_decode(self):
        with patch.object(web.barcode_stock, "product_detail", return_value=self.product):
            response = self.client.post("/api/v1/catalog/products/7/photo", data={"photo": (io.BytesIO(b"x" * (8 * 1024 * 1024 + 1)), "large.jpg")}, headers=self.headers)
        self.assertEqual(response.status_code, 413)
        self.assertFalse(Path(self.temp.name, "7.jpg").exists())


class StandaloneAuthTests(unittest.TestCase):
    def test_anonymous_bootstrap_login_rotation_and_logout(self):
        client = web.app.test_client()
        with patch.object(web, "INGRESS_MODE", False), patch.dict(os.environ, {"WEB_PASSWORD": "test-password"}):
            status = client.get("/api/v1/auth/status")
            token = status.json["csrf_token"]
            self.assertFalse(status.json["authenticated"])
            self.assertEqual(client.post("/api/v1/auth/login", json={"password": "test-password"}).status_code, 403)
            self.assertEqual(client.post("/api/v1/auth/login", json={"password": "wrong"}, headers={"X-CSRF-Token": token}).status_code, 401)
            login = client.post("/api/v1/auth/login", json={"password": "test-password"}, headers={"X-CSRF-Token": token})
            self.assertEqual(login.status_code, 200)
            self.assertNotEqual(login.json["csrf_token"], token)
            self.assertEqual(client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": login.json["csrf_token"]}).status_code, 200)
            denied = client.get("/api/v1/catalog/units")
            self.assertEqual(denied.status_code, 401)
            self.assertTrue(denied.is_json)

class PreviewPackagingTests(unittest.TestCase):
    def test_ingress_preview_has_root_base_and_safe_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            (root / "index.html").write_text('<html><head></head><body><script src="./assets/app.js"></script></body></html>')
            (root / "assets/app.js").write_text('console.log("preview")')
            with patch.object(web, "INGRESS_MODE", True), patch.dict(os.environ, {"FRONTEND_DIST_DIR": directory}):
                client = web.app.test_client()
                response = client.get('/react/', headers={"X-Ingress-Path": "/api/hassio_ingress/test-prefix"})
                self.assertIn(b'<base href="/api/hassio_ingress/test-prefix/">', response.data)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(client.get('/assets/app.js').status_code, 200)
                self.assertEqual(client.get('/assets/../index.html').status_code, 404)

    def test_standalone_preview_can_display_login_without_grocy(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "index.html").write_text('<html><head></head></html>')
            with patch.object(web, "INGRESS_MODE", False), patch.dict(os.environ, {"WEB_PASSWORD": "test-password", "FRONTEND_DIST_DIR": directory}), patch.object(web.barcode_stock, "grocy") as grocy:
                response = web.app.test_client().get('/react/')
                self.assertEqual(response.status_code, 200)
                grocy.assert_not_called()

class ConsumptionApiTests(unittest.TestCase):
    def test_consumption_is_csrf_protected_and_replays_safely(self):
        import uuid
        client = web.app.test_client()
        with tempfile.TemporaryDirectory() as directory, patch.object(web, "INGRESS_MODE", True), patch.dict(os.environ, {"STOCK_COMMAND_DB": directory + "/commands.sqlite3"}), patch.object(web.barcode_stock, "consume_product_quantity", return_value={"shopping_error": True}) as consume:
            payload = {"operation_id": str(uuid.uuid4()), "amount": "1", "expected_amount": "2", "add_to_list": True}
            denied = client.post('/api/v1/catalog/products/7/consume', json=payload)
            self.assertEqual(denied.status_code, 403)
            consume.assert_not_called()
            token = client.get('/api/v1/auth/status').json['csrf_token']
            for _ in range(2):
                response = client.post('/api/v1/catalog/products/7/consume', json=payload, headers={"X-CSRF-Token": token})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json["shopping_error"])
            consume.assert_called_once_with(7, "1", "2", True)
