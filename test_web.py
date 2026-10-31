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
        self.client.get("/?view=actions")
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
            response = self.client.get("/?view=associate")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="product-search"', response.data)
        self.assertIn(b'data-product-id="12"', response.data)
        self.assertIn(b'Nutella 350 g', response.data)
        self.assertIn(b'id="selected-product-id"', response.data)
        self.assertNotIn(b'<select name="product_id"', response.data)

    def test_inventory_home_and_actions_are_separate(self):
        token = self.login()
        with patch.object(web.barcode_stock, "inventory_with_shopping", return_value=[
            {"id": 5, "name": "Leche", "amount": "3", "unit": "Unidad", "shopping_amount": "2", "shopping_unit": "Unidad", "shopping_step": "1", "shopping_can_subtract": True},
            {"id": 8, "name": "Tomate", "amount": "1.5", "unit": "Kilogramo", "shopping_amount": "0.2", "shopping_unit": "kg", "shopping_step": "0.10", "shopping_can_subtract": True}]):
            response = self.client.get("/?view=inventory")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="inventory-search"', response.data)
        self.assertIn(b'Leche', response.data)
        self.assertIn(b'3', response.data)
        self.assertNotIn(b'<input name="barcode"', response.data)
        self.assertIn(b'/shopping/step/5/plus', response.data)
        self.assertIn(b'/shopping/step/8/minus', response.data)
        self.assertIn(b'0.2', response.data)
        self.assertIn(b'view=actions', response.data)
        self.assertTrue(token)

        with patch.object(web.barcode_stock, "inventory_with_shopping", side_effect=AssertionError("Should not fetch")):
            actions = self.client.get("/?view=actions")
        self.assertEqual(actions.status_code, 200)
        self.assertIn(b'class="action-grid"', actions.data)
        self.assertIn(b'view=associate', actions.data)
        self.assertNotIn(b'<input name="barcode"', actions.data)

    def test_new_product_form_has_unit_optional_barcode_and_initial_stock(self):
        self.login()
        with patch.object(web.barcode_stock, "new_product_units", return_value=[
                {"id": 2, "name": "Piece"}, {"id": 4, "name": "Kilogram"}]):
            response = self.client.get("/?view=add")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'A\xc3\xb1adir producto nuevo', response.data)
        self.assertIn(b'name="unit_id"', response.data)
        self.assertIn(b'name="initial_stock"', response.data)
        self.assertIn(b'step="0.01"', response.data)
        self.assertIn(b'Crear producto', response.data)
        self.assertNotIn(b'A\xc3\xb1adir 1 al stock', response.data)

    def test_existing_product_shows_link_to_edit_not_new_stock(self):
        token = self.login()
        with patch.object(web.barcode_stock, "create_catalog_product", return_value={
                "created": False, "product_id": 17, "name": "Tomate"}):
            with patch.object(web.barcode_stock, "new_product_units", return_value=[]):
                r = self.client.post("/barcode/add", data={
                    "csrf": token, "name": "Tomate", "barcode": "",
                    "unit_id": "4", "initial_stock": "2"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Ir a editar producto', r.data)
        self.assertIn(b'product_id=17', r.data)

    def test_new_product_redirects_to_its_sheet(self):
        token = self.login()
        with patch.object(web.barcode_stock, "create_catalog_product", return_value={
                "created": True, "product_id": 18, "name": "Tomate"}) as create:
            r = self.client.post("/barcode/add", data={
                "csrf": token, "name": "Tomate", "barcode": "",
                "unit_id": "4", "initial_stock": "0.5"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("product_id=18", r.headers["Location"])
        create.assert_called_once_with("Tomate", "", "4", "0.5", location_id=2, image_url=None)

    def test_consume_form_has_amount_and_shopping_checkbox(self):
        self.login()
        r = self.client.get("/?view=remove")
        self.assertIn(b'/barcode/remove-preview', r.data)
        self.assertNotIn(b'Confirmar: quitar 1 unidad', r.data)
        self.assertNotIn(b'<strong>Asociar c', self.client.get("/?view=actions").data)

    def test_consume_selected_quantity_and_replenish(self):
        token = self.login()
        with patch.object(web.barcode_stock, "consume_quantity", return_value={
                "amount": "0.50", "name": "Tomate",
                "shopping_added": True, "shopping_error": False}) as consume:
            with self.client.session_transaction() as sess:
                sess["remove_barcode"] = "1234567890123"
            r = self.client.post("/barcode/remove", data={
                "csrf": token, "barcode": "1234567890123", "amount": "0.50",
                "add_to_list": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'lista de la compra', r.data)
        consume.assert_called_once_with("1234567890123", "0.50", True)

    def test_action_forms_are_separate(self):
        self.login()
        for view, endpoint in [
            ("add", b'/barcode/add'), ("remove", b'/barcode/remove-preview'),
            ("associate", b'/barcode/associate'), ("photo", b'/barcode/photo'),
            ("ticket", b'/upload')]:
            result = self.client.get("/?view=" + view)
            self.assertEqual(result.status_code, 200, view)
            self.assertIn(endpoint, result.data, view)
            self.assertIn(b'Volver a acciones', result.data)
            self.assertIn(b'class="bottom-nav"', result.data)
        self.assertIn(b'class="ticket-table"', web.PAGE.encode("utf-8"))
        self.assertNotIn(b'class="ticket-table"', self.client.get("/?view=ticket").data)

    def test_inventory_backend_failure_has_no_fake_zeroes(self):
        self.login()
        with patch.object(web.barcode_stock, "inventory_with_shopping", side_effect=RuntimeError("offline")):
            response = self.client.get("/?view=inventory")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'No se ha podido consultar', response.data)

    def test_shopping_is_home_and_displays_grocy_items(self):
        self.login()
        with patch.object(web.barcode_stock, "shopping_list_snapshot", return_value=[
                {"id": 9, "product_id": 5, "name": "Leche", "amount": "2",
                 "unit": "Unidad", "done": False}]):
            with patch.object(web.barcode_stock, "inventory_with_shopping",
                              side_effect=AssertionError("inventory should not load")):
                response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Lista de la compra', response.data)
        self.assertIn(b'Leche', response.data)
        self.assertIn(b'/shopping/9/toggle', response.data)
        self.assertIn(b'/shopping/9/remove', response.data)
        self.assertNotIn(b'id="inventory-search"', response.data)

    def test_pantry_adds_one_product_to_shopping_list(self):
        token = self.login()
        with patch.object(web.barcode_stock, "add_to_shopping_list", return_value="Leche") as add:
            with patch.object(web.barcode_stock, "shopping_list_snapshot", return_value=[]):
                response = self.client.post("/shopping/add/5", data={"csrf": token, "amount": "1.50", "unit_id": "4"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Leche', response.data)
        add.assert_called_once_with(5, "1.50", "4")

    def test_shopping_add_screen_has_amount_and_unit(self):
        self.login()
        with patch.object(web.barcode_stock, "shopping_product_options", return_value={
                "id": 5, "name": "Tomate", "units": [
                    {"id": 4, "name": "Kilogramo", "factor": "1"}]}):
            response = self.client.get("/?view=shopping_add&product_id=5")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="amount"', response.data)
        self.assertIn(b'name="unit_id"', response.data)
        self.assertIn(b'step="0.01"', response.data)

    def test_inline_shopping_buttons_change_quantity_without_form_page(self):
        token = self.login()
        with patch.object(web.barcode_stock, "change_shopping_quantity") as change:
            response = self.client.post("/shopping/step/5/plus", data={"csrf": token})
            self.assertEqual(response.status_code, 302)
            self.assertIn("view=inventory", response.headers["Location"])
            change.assert_called_once_with(5, "plus")
            response = self.client.post("/shopping/step/5/minus", data={"csrf": token})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(change.call_count, 2)

    def test_shopping_toggle_and_remove(self):
        token = self.login()
        with patch.object(web.barcode_stock, "update_shopping_list_item") as toggle:
            self.assertEqual(self.client.post("/shopping/9/toggle",
                data={"csrf": token, "done": "1"}).status_code, 302)
            toggle.assert_called_once_with(9, True)
        with patch.object(web.barcode_stock, "remove_shopping_list_item") as remove:
            self.assertEqual(self.client.post("/shopping/9/remove",
                data={"csrf": token}).status_code, 302)
            remove.assert_called_once_with(9)

    def test_product_sheet_from_inventory_and_picture_inside_sheet(self):
        token = self.login()
        with patch.object(web.barcode_stock, "inventory_with_shopping", return_value=[
            {"id": 5, "name": "Aroma de vainilla", "amount": "1", "unit": "Unidad", "shopping_amount": "0", "shopping_unit": "Unidad", "shopping_step": "1", "shopping_can_subtract": False}]):
            home = self.client.get("/?view=inventory")
        self.assertIn(b'view=product', home.data)
        self.assertIn(b'product_id=5', home.data)
        self.assertNotIn(b'Buscar fotograf', self.client.get("/?view=actions").data)
        with patch.object(web.barcode_stock, "product_detail", return_value={
                "id": 5, "name": "Aroma de vainilla", "pack_size": 4,
                "description": "", "barcodes": ["1234567890123"],
                "unit_id": 2, "units": [{"id": 2, "name": "Unidad"}, {"id": 4, "name": "Kilogramo"}], "stock_amount": "1.25"}):
            sheet = self.client.get("/?view=product&product_id=5")
            self.assertEqual(sheet.status_code, 200)
            self.assertIn(b'name="pack_size"', sheet.data)
            self.assertIn(b'value="4"', sheet.data)
            self.assertIn(b'/product/5/photo', sheet.data)
            self.assertIn(b'/product/5/edit', sheet.data)
            with patch.object(web.barcode_stock, "update_product_info",
                              return_value={"id": 5, "name": "Aroma", "pack_size": 4}) as change:
                response = self.client.post("/product/5/edit", data={
                    "csrf": token, "name": "Aroma", "pack_size": "4", "unit_id": "2"})
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'Existencias sin cambios', response.data)
                change.assert_called_once_with(5, "Aroma", "4", "2")

    def test_product_picture_lookup_saves_reference(self):
        token = self.login()
        with patch.object(web.barcode_stock, "product_detail", return_value={
                "id": 5, "name": "Aroma", "pack_size": 4, "description": "",
                "barcodes": ["1234567890123"],
                "unit_id": 2, "units": [{"id": 2, "name": "Unidad"}], "stock_amount": "1"}):
            with patch.object(web.product_images, "lookup_image", return_value={
                    "name": "Aroma", "image_url": "https://images.openfoodfacts.org/a.jpg",
                    "source_url": "https://world.openfoodfacts.org/a"}) as lookup:
                with patch.object(web.barcode_stock, "save_product_photo") as save:
                    response = self.client.post("/product/5/photo", data={"csrf": token})
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b'Fotograf', response.data)
                    lookup.assert_called_once_with("1234567890123")
                    save.assert_called_once_with(5, "https://images.openfoodfacts.org/a.jpg")

    def test_photo_lookup_api_returns_found_image(self):
        self.login()
        with patch.object(web.product_images, "lookup_image", return_value={
                "image_url": "https://images.openfoodfacts.org/sample.jpg"}):
            r = self.client.get("/photo/lookup?barcode=1234567890123")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["image_url"], "https://images.openfoodfacts.org/sample.jpg")

    def test_pack_size_field_only_shows_when_unit_is_pack(self):
        self.login()
        with patch.object(web.barcode_stock, "product_detail", return_value={
                "id": 5, "name": "Arroz", "is_pack": False,
                "image_url": None, "pack_size": 1, "unit_id": 2,
                "units": [{"id": 2, "name": "Piece"}, {"id": 3, "name": "Pack"}],
                "stock_amount": "0", "barcodes": []}):
            r = self.client.get("/?view=product&product_id=5")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'id="pack-size-fields" hidden', r.data)

    def test_product_sheet_displays_quantity_unit_and_barcode_actions(self):
        self.login()
        with patch.object(web.barcode_stock, "product_detail", return_value={
                "id": 5, "name": "Tomate en rama", "pack_size": 1,
                "description": "", "barcodes": [],
                "unit_id": 4,
                "units": [{"id": 2, "name": "Unidad"}, {"id": 4, "name": "Kilogramo"}],
                "stock_amount": "1.25"}):
            response = self.client.get("/?view=product&product_id=5")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="unit_id"', response.data)
        self.assertIn(b'name="desired_amount"', response.data)
        self.assertIn(b'step="0.01"', response.data)
        self.assertIn(b'/product/5/barcode', response.data)

    def test_stock_edit_saves_without_confirmation(self):
        token = self.login()
        with patch.object(web.barcode_stock, "prepare_stock_adjustment", return_value={
                "product_id": 5, "before": "1.25", "after": "1.50",
                "difference": "0.25", "direction": "add"}) as preview:
            with patch.object(web.barcode_stock, "apply_stock_adjustment", return_value={
                    "after": "1.50"}) as commit:
                r = self.client.post("/product/5/stock-save", data={
                    "csrf": token, "desired_amount": "1.50", "expected_amount": "1.25"})
                self.assertEqual(r.status_code, 200)
                self.assertIn(b'Stock actualizado', r.data)
                preview.assert_called_once_with(5, "1.50", "1.25")
                commit.assert_called_once()
        self.assertNotIn(b'Confirmar cambio de existencias', r.data)

    def test_stock_edit_rejects_stale_values(self):
        token = self.login()
        with patch.object(web.barcode_stock, "prepare_stock_adjustment",
                          side_effect=web.barcode_stock.BarcodeError("Stock actualizado por otro")):
            with patch.object(web.barcode_stock, "apply_stock_adjustment") as commit:
                r = self.client.post("/product/5/stock-save", data={
                    "csrf": token, "desired_amount": "1.50", "expected_amount": "1.25"})
                self.assertEqual(r.status_code, 409)
                commit.assert_not_called()

    def test_camera_scanner_available_for_all_barcode_actions(self):
        self.login()
        with patch.object(web.barcode_stock, "list_products", return_value=[]):
            response = self.client.get("/?view=add")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'class="scan-trigger"'), 1)
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
