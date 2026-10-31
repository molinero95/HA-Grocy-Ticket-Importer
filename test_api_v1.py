"""Read-only API contract tests for the incremental React migration."""
import unittest
import os
from unittest.mock import patch

with patch.dict(os.environ, {"WEB_PASSWORD": "test-password", "WEB_SESSION_SECRET": "test-secret-key"}, clear=False):
    import web


class ShoppingApiTests(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()

    def test_anonymous_request_is_rejected_without_reading_grocy(self):
        with patch.object(web, "INGRESS_MODE", False), patch.object(web.barcode_stock, "shopping_list_snapshot") as read:
            response = self.client.get("/api/v1/shopping")
            self.assertEqual(response.status_code, 401)
            read.assert_not_called()

    def test_authenticated_snapshot_is_read_only(self):
        items = [{"id": 1, "name": "Arroz", "amount": 1, "unit": "unidad", "done": False, "product_id": None, "image_url": None}]
        matches = [{"key": "arroz", "name": "Arroz", "candidates": [{"id": 2, "name": "Arroz basmati"}, {"id": 3, "name": "Arroz integral"}]}]
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "shopping_list_snapshot", return_value=items), patch.object(web.shopping_match_queue, "pending", return_value=matches):
            response = self.client.get("/api/v1/shopping")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["items"], items)
        self.assertEqual(response.json["pending_matches"], matches)

    def test_grocy_failure_returns_structured_error(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "shopping_list_snapshot", side_effect=RuntimeError("unavailable")):
            response = self.client.get("/api/v1/shopping")
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.json["shopping_error"])


if __name__ == "__main__":
    unittest.main()
