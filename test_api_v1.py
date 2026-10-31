"""Read-only API contract tests for the incremental React migration."""
import unittest
import os
from unittest.mock import patch

with patch.dict(os.environ, {"WEB_PASSWORD": "test-password", "WEB_SESSION_SECRET": "test-secret-key"}, clear=False):
    import web


class ShoppingApiTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"WEB_PASSWORD": "test-password", "WEB_SESSION_SECRET": "test-secret-key"}, clear=False)
        env.start()
        self.addCleanup(env.stop)
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

    def test_variant_write_requires_csrf(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.variant_catalog, "save_variant") as save:
            response = self.client.post("/api/v1/products/3/variants", json={"barcode": "8412345678901", "name": "Leche"})
        self.assertEqual(response.status_code, 403)
        save.assert_not_called()

    def test_variant_write_rejects_conflicting_barcode(self):
        payload = {"barcode": "8412345678901", "name": "Leche", "supermarket": "A", "brand": "", "units_per_purchase": "1"}
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.variant_catalog, "save_variant", side_effect=ValueError("belongs to another product")) as save:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            response = self.client.post("/api/v1/products/3/variants", json=payload, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 409)
        save.assert_called_once()

    def test_variants_read_only_and_product_must_exist(self):
        catalog = [{"id": 3, "name": "Leche"}]
        variants = [{"barcode": "8412345678901", "name": "Leche A", "supermarket": "A", "brand": "", "units_per_purchase": 1}]
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "list_products", return_value=catalog), patch.object(web.variant_catalog, "variants_for_product", return_value=variants) as get_variants:
            self.assertEqual(self.client.get("/api/v1/products/9/variants").status_code, 404)
            response = self.client.get("/api/v1/products/3/variants")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["variants"], variants)
        get_variants.assert_called_once_with(3)

    def test_inventory_returns_combined_stock_and_shopping(self):
        rows = [{"id": 8, "name": "Leche", "amount": "2", "unit": "ud.", "shopping_amount": "1"}]
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "inventory_with_shopping", return_value=rows):
            response = self.client.get("/api/v1/inventory")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["items"], rows)

    def test_barcode_lookup_filters_by_product_id_without_redirect(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "find_product", return_value={"id": 8}):
            response = self.client.get("/api/v1/barcodes/8412345678901")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["product_id"], 8)

    def test_shopping_step_requires_csrf(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "change_shopping_quantity") as update:
            response = self.client.post("/api/v1/shopping/products/8/step", json={"direction": "plus"})
        self.assertEqual(response.status_code, 403)
        update.assert_not_called()

    def test_write_requires_csrf_and_never_mutates_without_it(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "update_shopping_list_item") as update:
            response = self.client.post("/api/v1/shopping/7/toggle", json={"done": True})
        self.assertEqual(response.status_code, 403)
        update.assert_not_called()

    def test_toggle_requires_boolean_and_calls_backend_once(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "update_shopping_list_item") as update:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            headers = {"X-CSRF-Token": token}
            self.assertEqual(self.client.post("/api/v1/shopping/7/toggle", json={"done": 1}, headers=headers).status_code, 400)
            self.assertEqual(self.client.post("/api/v1/shopping/7/toggle", json={"done": True}, headers=headers).status_code, 200)
        update.assert_called_once_with(7, True)

    def test_alexa_choice_rejects_stale_candidate(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.shopping_match_queue, "choose", side_effect=ValueError("stale")) as choose:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            response = self.client.post("/api/v1/alexa/matches/arroz/choose", json={"product_id": 42}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 409)
        choose.assert_called_once()

    def test_grocy_failure_returns_structured_error(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "shopping_list_snapshot", side_effect=RuntimeError("unavailable")):
            response = self.client.get("/api/v1/shopping")
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.json["shopping_error"])


if __name__ == "__main__":
    unittest.main()
