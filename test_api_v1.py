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


    def test_receipt_upload_requires_csrf(self):
        from io import BytesIO
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.extract, "extract") as extract:
            response = self.client.post("/api/v1/receipts", data={"ticket": (BytesIO(b"sample"), "ticket.pdf")})
        self.assertEqual(response.status_code, 403)
        extract.assert_not_called()

    def test_receipt_upload_rejects_invalid_format(self):
        from io import BytesIO
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.extract, "extract") as extract:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            response = self.client.post("/api/v1/receipts", data={"ticket": (BytesIO(b"sample"), "ticket.exe")}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 400)
        extract.assert_not_called()

    def test_receipt_commit_requires_preview(self):
        from unittest.mock import Mock
        with patch.object(web, "INGRESS_MODE", True), patch.object(web, "run_import") as importer:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            with self.client.session_transaction() as session:
                session["receipt_id"] = "a" * 32
            response = self.client.post("/api/v1/receipts/" + "a" * 32 + "/commit", headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 403)
        importer.assert_not_called()

    def test_catalog_create_requires_csrf(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "create_catalog_product") as create:
            response = self.client.post("/api/v1/catalog/products", json={"name": "Arroz", "unit_id": 1})
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_catalog_create_returns_existing_product_without_duplication(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "create_catalog_product", return_value={"created": False, "product_id": 7, "name": "Arroz"}) as create:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            response = self.client.post("/api/v1/catalog/products", json={"name": "Arroz", "unit_id": 1}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["created"])
        create.assert_called_once()

    def test_catalog_edit_requires_csrf(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "update_product_info") as edit:
            response = self.client.patch("/api/v1/catalog/products/3", json={"name": "Arroz integral"})
        self.assertEqual(response.status_code, 403)
        edit.assert_not_called()

    def test_catalog_edit_preserves_stock(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "update_product_info", return_value={"id": 3, "name": "Arroz integral", "unit_id": 1}) as edit:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            response = self.client.patch("/api/v1/catalog/products/3", json={"name": "Arroz integral"}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 200)
        edit.assert_called_once_with(3, "Arroz integral", "1", None)

    def test_catalog_barcode_rejects_conflict_without_writing(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "associate_product_barcode", side_effect=web.barcode_stock.BarcodeError("Código en otro producto")) as save:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            response = self.client.post("/api/v1/catalog/products/7/barcodes", json={"barcode": "8412345678901"}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 409)
        save.assert_called_once()

    def test_catalog_stock_rejects_stale_quantity_without_writing(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "prepare_stock_adjustment", side_effect=web.barcode_stock.BarcodeError("stock changed")), patch.object(web.barcode_stock, "apply_stock_adjustment") as apply:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            response = self.client.post("/api/v1/catalog/products/7/stock", json={"desired_amount": "5", "expected_amount": "2"}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 409)
        apply.assert_not_called()

    def test_catalog_barcode_delete_requires_csrf(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "remove_product_barcode") as remove:
            response = self.client.delete("/api/v1/catalog/products/7/barcodes/8412345678901")
        self.assertEqual(response.status_code, 403)
        remove.assert_not_called()

    def test_catalog_barcode_delete_rejects_variant(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "remove_product_barcode", side_effect=web.barcode_stock.BarcodeError("variant")) as remove:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            response = self.client.delete("/api/v1/catalog/products/7/barcodes/8412345678901", headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 409)
        remove.assert_called_once_with(7, "8412345678901")

    def test_merge_preview_rejects_same_product_without_writes(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "product_detail") as detail:
            response = self.client.get("/api/v1/catalog/merge-preview?source_id=7&target_id=7")
        self.assertEqual(response.status_code, 400)
        detail.assert_not_called()

    def test_merge_preview_is_read_only_and_warns_on_different_units(self):
        source = {"id": 1, "name": "Leche", "stock_amount": "2", "unit_id": 1, "pack_size": 1, "barcodes": ["8412345678901"]}
        target = {"id": 2, "name": "Leche entera", "stock_amount": "3", "unit_id": 2, "pack_size": 1, "barcodes": []}
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "product_detail", side_effect=[source, target]), patch("variant_catalog.variants_for_product", return_value=[]):
            response = self.client.get("/api/v1/catalog/merge-preview?source_id=1&target_id=2")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["merge_allowed"])
        self.assertTrue(any("unidades" in warning for warning in response.json["warnings"]))

    def test_merge_preview_rejects_same_product(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "product_detail") as detail:
            response = self.client.get("/api/v1/catalog/merge-preview?source_id=7&target_id=7")
        self.assertEqual(response.status_code, 400)
        detail.assert_not_called()

    def test_merge_preview_never_writes_stock(self):
        def product(pid):
            return {"id": pid, "name": "Producto", "unit_id": 2, "purchase_unit_id": 2, "pack_size": 1, "stock_amount": "3", "barcodes": []}
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.barcode_stock, "product_detail", side_effect=product), patch("variant_catalog.variants_for_product", return_value=[]), patch.object(web.barcode_stock, "grocy") as grocy:
            response = self.client.get("/api/v1/catalog/merge-preview?source_id=7&target_id=8")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["can_merge"])
        self.assertTrue(response.json["blockers"])
        grocy.assert_not_called()

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

    def test_alexa_keep_original_does_not_choose_a_product(self):
        with patch.object(web, "INGRESS_MODE", True), patch.object(web.shopping_match_queue, "keep_original") as keep, patch.object(web.shopping_match_queue, "choose") as choose:
            token = self.client.get("/api/v1/session").json["csrf_token"]
            response = self.client.post("/api/v1/alexa/matches/arroz/choose", json={"product_id": 0}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 200)
        keep.assert_called_once()
        choose.assert_not_called()

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
