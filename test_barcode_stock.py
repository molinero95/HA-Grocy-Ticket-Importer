"""Barcode and photo tests. No real Grocy writes or network calls."""
import json
import unittest
from unittest.mock import Mock, patch

import barcode_stock
import product_images

PRODUCTS = [{"id": 5, "name": "Leche", "qu_id_stock": 2},
            {"id": 8, "name": "Pasta", "qu_id_stock": 2}]

class ProductCreationTests(unittest.TestCase):
    @patch("barcode_stock.grocy")
    def test_existing_name_or_barcode_returns_edit_target_without_writes(self, api):
        def fake(method, path, body=None):
            self.assertEqual(method, "GET")
            return {
                "objects/quantity_units": [{"id": 2, "name": "Piece"}],
                "objects/products": [{"id": 5, "name": "  Leche  "}, {"id": 7, "name": "Agua"}],
                "objects/product_barcodes": [{"product_id": 7, "barcode": "1234567890123"}],
            }[path]
        api.side_effect = fake
        by_name = barcode_stock.create_catalog_product("leche", "", 2, "3")
        self.assertEqual(by_name["product_id"], 5)
        self.assertFalse(by_name["created"])
        by_barcode = barcode_stock.create_catalog_product("Producto distinto", "1234567890123", 2, "3")
        self.assertEqual(by_barcode["product_id"], 7)
        self.assertFalse(by_barcode["created"])
        self.assertFalse(any(c.args[0] != "GET" for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_new_product_zero_stock_never_creates_stock_movement(self, api):
        posts = []
        def fake(method, path, body=None):
            if method == "GET":
                return {
                    "objects/quantity_units": [{"id": 2, "name": "Piece"}, {"id": 4, "name": "Kilogram"}],
                    "objects/products": [], "objects/product_barcodes": [],
                }[path]
            posts.append((path, body))
            return {"created_object_id": 17}
        api.side_effect = fake
        result = barcode_stock.create_catalog_product("Tomate", "", 4, "0")
        self.assertTrue(result["created"])
        self.assertEqual(result["product_id"], 17)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][1]["qu_id_stock"], 4)
        self.assertEqual(posts[0][1]["qu_id_purchase"], 4)

    @patch("barcode_stock.grocy")
    def test_new_product_initial_stock_uses_selected_unit(self, api):
        posts = []
        def fake(method, path, body=None):
            if method == "GET":
                return {
                    "objects/quantity_units": [{"id": 4, "name": "Kilogram"}],
                    "objects/products": [], "objects/product_barcodes": [],
                }[path]
            posts.append((path, body))
            return {"created_object_id": 17}
        api.side_effect = fake
        barcode_stock.create_catalog_product("Tomate", "1234567890123", 4, "0,50")
        self.assertEqual([p for p, _ in posts], [
            "objects/products", "objects/product_barcodes", "stock/products/17/add"])
        self.assertEqual(posts[-1][1]["amount"], 0.5)

    @patch("barcode_stock.grocy")
    def test_new_pack_of_five_creates_piece_stock(self, api):
        posts = []
        def fake(method, path, body=None):
            if method == "GET":
                return {
                    "objects/quantity_units": [
                        {"id": 2, "name": "Piece"}, {"id": 3, "name": "Pack"}],
                    "objects/products": [], "objects/product_barcodes": [],
                }[path]
            posts.append((path, body))
            return {"created_object_id": 19}
        api.side_effect = fake
        result = barcode_stock.create_catalog_product(
            "Yogures", "", 3, "2", pack_size="5")
        self.assertTrue(result["created"])
        self.assertEqual(posts[0][1]["qu_id_stock"], 2)
        self.assertEqual(posts[0][1]["qu_id_purchase"], 3)
        self.assertEqual(posts[0][1]["qu_factor_purchase_to_stock"], 5)
        self.assertEqual(posts[-1][0], "stock/products/19/add")
        self.assertEqual(posts[-1][1]["amount"], 10.0)

    @patch("barcode_stock.grocy")
    def test_invalid_creation_never_writes(self, api):
        for qty in ("-1", "1.123", "NaN"):
            with self.assertRaises(barcode_stock.BarcodeError):
                barcode_stock.create_catalog_product("Tomate", "", 4, qty)
        api.assert_not_called()


class BarcodeTests(unittest.TestCase):
    @patch("barcode_stock.grocy")
    def test_link_existing_product_does_not_write_stock(self, api):
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/products":
                return PRODUCTS
            if method == "GET" and path == "objects/product_barcodes":
                return []
            if method == "POST" and path == "objects/product_barcodes":
                return {"created_object_id": 88}
            raise AssertionError((method, path))
        api.side_effect = fake
        result = barcode_stock.associate_barcode("1234567890123", 5)
        self.assertFalse(result["already_linked"])
        api.assert_any_call("POST", "objects/product_barcodes",
                            {"product_id": 5, "barcode": "1234567890123"})
        self.assertFalse(any(c.args[0] == "POST" and c.args[1].startswith("stock/")
                             for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_existing_barcode_with_other_product_rejected(self, api):
        def fake(method, path, body=None):
            if path == "objects/products":
                return PRODUCTS
            if path == "objects/product_barcodes":
                return [{"barcode": "1234567890123", "product_id": 8}]
            raise AssertionError((method, path))
        api.side_effect = fake
        with self.assertRaises(barcode_stock.BarcodeError):
            barcode_stock.associate_barcode("1234567890123", 5)
        self.assertFalse(any(c.args[0] == "POST" for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_removal_consumes_one_not_delete(self, api):
        def fake(method, path, body=None):
            if path == "objects/product_barcodes":
                return [{"barcode": "1234567890123", "product_id": 5}]
            if path == "objects/products":
                return PRODUCTS
            if path == "stock/products/5":
                return {"stock_amount": 3}
            if method == "POST" and path == "stock/products/5/consume":
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        barcode_stock.remove_one("1234567890123")
        api.assert_any_call("POST", "stock/products/5/consume", {"amount": 1, "spoiled": False})
        self.assertFalse(any("DELETE" == c.args[0] for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_consume_quantity_and_replenish_purchase_list(self, api):
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/product_barcodes":
                return [{"product_id": 5, "barcode": "1234567890123"}]
            if method == "GET" and path == "objects/products":
                return PRODUCTS
            if method == "GET" and path == "stock/products/5":
                return {"stock_amount": "2"}
            if method == "GET" and path == "objects/products/5":
                return {"id": 5, "name": "Leche", "qu_id_stock": 2}
            if method == "POST":
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        result = barcode_stock.consume_quantity("1234567890123", "0,50", True)
        self.assertTrue(result["shopping_added"])
        api.assert_any_call("POST", "stock/products/5/consume", {"amount": 0.5, "spoiled": False})
        api.assert_any_call("POST", "stock/shoppinglist/add-product",
                            {"product_id": 5, "list_id": 1, "product_amount": 0.5, "qu_id": 2})

    @patch("barcode_stock.grocy")
    def test_consumption_rejects_more_than_stock_and_three_decimals(self, api):
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/product_barcodes":
                return [{"product_id": 5, "barcode": "1234567890123"}]
            if method == "GET" and path == "objects/products":
                return PRODUCTS
            if method == "GET" and path == "stock/products/5":
                return {"stock_amount": "1"}
            raise AssertionError((method, path))
        api.side_effect = fake
        for qty in ("1.01", "0.001", "-1", "NaN"):
            with self.assertRaises(barcode_stock.BarcodeError):
                barcode_stock.consume_quantity("1234567890123", qty)
        self.assertFalse(any(c.args[0] == "POST" for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_replenish_failure_does_not_repeat_consumption(self, api):
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/product_barcodes":
                return [{"product_id": 5, "barcode": "1234567890123"}]
            if method == "GET" and path == "objects/products":
                return PRODUCTS
            if method == "GET" and path == "stock/products/5":
                return {"stock_amount": "2"}
            if method == "GET" and path == "objects/products/5":
                return {"id": 5, "qu_id_stock": 2}
            if method == "POST" and path == "stock/shoppinglist/add-product":
                raise RuntimeError("Grocy shopping-list failure")
            if method == "POST" and path == "stock/products/5/consume":
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        result = barcode_stock.consume_quantity("1234567890123", "1", True)
        self.assertTrue(result["shopping_error"])
        self.assertFalse(result["shopping_added"])
        self.assertEqual(sum(c.args[0] == "POST" and c.args[1] == "stock/products/5/consume"
                             for c in api.call_args_list), 1)

    @patch("barcode_stock.grocy")
    def test_no_stock_no_consumption(self, api):
        def fake(method, path, body=None):
            if path == "objects/product_barcodes":
                return [{"barcode": "1234567890123", "product_id": 5}]
            if path == "objects/products":
                return PRODUCTS
            if path == "stock/products/5":
                return {"stock_amount": 0}
            raise AssertionError((method, path))
        api.side_effect = fake
        with self.assertRaises(barcode_stock.BarcodeError):
            barcode_stock.remove_one("1234567890123")

    @patch("barcode_stock.grocy")
    def test_inventory_snapshot_reads_all_quantities_with_three_requests(self, api):
        def fake(method, path, body=None):
            self.assertEqual(method, "GET")
            if path == "objects/products":
                return PRODUCTS + [{"id": 9, "name": "Sin stock", "qu_id_stock": 2}]
            if path == "objects/quantity_units":
                return [{"id": 2, "name": "Unidad"}]
            if path == "stock":
                return [{"product_id": 5, "amount": 3}, {"product_id": 8, "amount": "1.5"}]
            raise AssertionError(f"Unexpected API call: {path}")
        api.side_effect = fake
        result = barcode_stock.inventory_snapshot()
        self.assertEqual([(p["name"], p["amount"], p["unit"]) for p in result],
                         [("Leche", "3", "Unidad"), ("Pasta", "1.5", "Unidad"),
                          ("Sin stock", "0", "Unidad")])
        self.assertEqual(api.call_count, 3)
        self.assertFalse(any(c.args[0] != "GET" for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_inventory_snapshot_failure_never_silently_claims_zero(self, api):
        def fake(method, path, body=None):
            if path == "objects/products":
                return PRODUCTS
            if path == "objects/quantity_units":
                return []
            if path == "stock":
                raise RuntimeError("Service unavailable")
            raise AssertionError(path)
        api.side_effect = fake
        with self.assertRaises(RuntimeError):
            barcode_stock.inventory_snapshot()

    @patch("barcode_stock.grocy")
    def test_inventory_snapshot_rejects_malformed_stock(self, api):
        api.side_effect = [PRODUCTS, [], [{"product_id": 5}]]
        with self.assertRaises(KeyError):
            barcode_stock.inventory_snapshot()

    @patch("barcode_stock.grocy")
    def test_edit_product_pack_preserves_stock_and_description(self, api):
        existing = {"id": 7, "name": "Vainilla", "description": "Uso repostería", "qu_id_stock": 2, "qu_id_purchase": 3}
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/products/7":
                return existing
            if method == "PUT" and path == "objects/products/7":
                self.assertEqual(body["name"], "Aroma vainilla")
                self.assertIn("Uso repostería", body["description"])
                self.assertIn("unidades_por_envase=4", body["description"])
                self.assertIn("\n[Despensa: unidades_por_envase=4]", body["description"])
                existing.update(body)
                return {}
            if method == "GET" and path == "objects/product_barcodes":
                return [{"product_id": 7, "barcode": "1234567890123"}]
            if method == "GET" and path == "objects/quantity_units":
                return [{"id": 2, "name": "Piece"}, {"id": 3, "name": "Pack"}]
            if method == "GET" and path == "stock/products/7":
                return {"stock_amount": 0}
            raise AssertionError((method, path))
        api.side_effect = fake
        result = barcode_stock.update_product_info(7, "Aroma vainilla", "4")
        self.assertEqual(result["pack_size"], 4)
        detail = barcode_stock.product_detail(7)
        self.assertEqual(detail["pack_size"], 4)
        self.assertEqual(detail["description"], "Uso repostería")
        self.assertFalse(any(c.args[0] == "POST" for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_reediting_pack_updates_existing_marker_without_duplicates(self, api):
        product = {"id": 7, "name": "Vainilla",
                   "description": "Nota antigua\n[Despensa: unidades_por_envase=4]", "qu_id_stock": 2, "qu_id_purchase": 3}
        def fake(method, path, body=None):
            if method == "GET":
                return [{"id": 2, "name": "Piece"}, {"id": 3, "name": "Pack"}] if path == "objects/quantity_units" else product
            if method == "PUT":
                self.assertEqual(body["description"].count("unidades_por_envase="), 1)
                self.assertIn("unidades_por_envase=6", body["description"])
                product.update(body)
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        barcode_stock.update_product_info(7, "Vainilla", "6")
        self.assertEqual(product["description"], "Nota antigua\n[Despensa: unidades_por_envase=6]")

    @patch("barcode_stock.grocy")
    def test_piece_hides_pack_size_and_preserves_photo(self, api):
        product = {"id": 7, "name": "Leche", "qu_id_stock": 2,
                   "description": "Notas\n[Despensa: imagen=https://images.openfoodfacts.org/images/products/a.jpg]"}
        def fake(method, path, body=None):
            if path == "objects/products/7" and method == "GET":
                return product
            if path == "objects/quantity_units":
                return [{"id": 2, "name": "Piece"}, {"id": 3, "name": "Pack"}]
            if path == "objects/product_barcodes":
                return []
            if path == "stock/products/7":
                return {"stock_amount": "1"}
            if path == "objects/products/7" and method == "PUT":
                self.assertIn("imagen=https://images.openfoodfacts.org", body["description"])
                self.assertNotIn("unidades_por_envase=", body["description"])
                product.update(body)
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        barcode_stock.update_product_info(7, "Leche", "4", "2")
        detail = barcode_stock.product_detail(7)
        self.assertFalse(detail["is_pack"])
        self.assertEqual(detail["pack_size"], 1)
        self.assertEqual(detail["image_url"], "https://images.openfoodfacts.org/images/products/a.jpg")

    @patch("barcode_stock.grocy")
    def test_piece_to_pack_preserves_piece_stock_and_sets_purchase_conversion(self, api):
        def fake(method, path, body=None):
            if path == "objects/products/7" and method == "GET":
                return {"id": 7, "name": "Leche", "qu_id_stock": 2}
            if path == "objects/quantity_units":
                return [{"id": 2, "name": "Piece"}, {"id": 3, "name": "Pack"}]
            if method == "PUT" and path == "objects/products/7":
                self.assertEqual(body["qu_id_purchase"], 3)
                self.assertEqual(body["qu_factor_purchase_to_stock"], 6)
                self.assertNotIn("qu_id_stock", body)
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        result = barcode_stock.update_product_info(7, "Leche", "6", "3")
        self.assertEqual(result["unit_id"], 2)
        self.assertFalse(any(c.args[0] == "POST" for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_invalid_pack_count_never_writes(self, api):
        for invalid in ("0", "-1", "1001", "not-a-number"):
            with self.assertRaises(barcode_stock.BarcodeError):
                barcode_stock.update_product_info(7, "Vainilla", invalid)
        api.assert_not_called()

    @patch("barcode_stock.grocy")
    def test_inventory_inline_shopping_quantities(self, api):
        def fake(method, path, body=None):
            if method != "GET":
                raise AssertionError((method, path))
            if path == "objects/products":
                return [{"id": 7, "name": "Tomate", "qu_id_stock": 4},
                        {"id": 8, "name": "Leche", "qu_id_stock": 2}]
            if path == "objects/quantity_units":
                return [{"id": 4, "name": "Kilogram"}, {"id": 2, "name": "Piece"}]
            if path == "stock":
                return [{"product_id": 7, "amount": "1.2"}]
            if path == "objects/shopping_list":
                return [{"id": 1, "product_id": 7, "amount": "0.3", "done": 0},
                        {"id": 2, "product_id": 8, "amount": "2", "done": 0}]
            raise AssertionError((method, path))
        api.side_effect = fake
        rows = barcode_stock.inventory_with_shopping()
        self.assertEqual(rows[0]["shopping_step"], "1")
        self.assertEqual(rows[0]["shopping_amount"], "2")
        self.assertEqual(rows[1]["shopping_step"], "0.10")
        self.assertEqual(rows[1]["shopping_amount"], "0.3")

    @patch("barcode_stock.grocy")
    def test_shopping_step_add_and_remove_with_correct_units(self, api):
        calls = []
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/products":
                return [{"id": 7, "name": "Tomate", "qu_id_stock": 4}]
            if method == "GET" and path == "objects/quantity_units":
                return [{"id": 4, "name": "Kilogram"}]
            if method == "GET" and path == "objects/shopping_list":
                return [{"id": 1, "product_id": 7, "amount": "0.3", "done": 0}]
            if method == "POST":
                calls.append((path, body))
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        barcode_stock.change_shopping_quantity(7, "plus")
        barcode_stock.change_shopping_quantity(7, "minus")
        self.assertEqual(calls[0], ("stock/shoppinglist/add-product",
            {"product_id": 7, "list_id": 1, "product_amount": 0.1, "qu_id": 4}))
        self.assertEqual(calls[1], ("stock/shoppinglist/remove-product",
            {"product_id": 7, "list_id": 1, "product_amount": 0.1}))
        with self.assertRaises(barcode_stock.BarcodeError):
            barcode_stock.change_shopping_quantity(7, "invalid")

    @patch("barcode_stock.grocy")
    def test_shopping_list_snapshot_reads_default_list(self, api):
        def fake(method, path, body=None):
            if path == "objects/shopping_list":
                return [{"id": 9, "product_id": 7, "amount": "1.50", "qu_id": 4,
                         "shopping_list_id": 1, "done": 0},
                        {"id": 10, "product_id": 8, "shopping_list_id": 2}]
            if path == "objects/products":
                return [{"id": 7, "name": "Tomate en rama", "qu_id_stock": 4}]
            if path == "objects/quantity_units":
                return [{"id": 4, "name": "Kilogramo"}]
            raise AssertionError((method, path))
        api.side_effect = fake
        self.assertEqual(barcode_stock.shopping_list_snapshot(), [{
            "id": 9, "product_id": 7, "name": "Tomate en rama",
            "amount": "1.5", "unit": "Kilogramo", "done": False}])

    @patch("barcode_stock.grocy")
    def test_shopping_add_with_quantity_and_unit_conversion(self, api):
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/products/7":
                return {"id": 7, "name": "Tomate", "qu_id_stock": 4,
                        "qu_id_purchase": 5, "qu_factor_purchase_to_stock": 0.5}
            if method == "GET" and path == "objects/quantity_units":
                return [{"id": 4, "name": "Kilogramo"}, {"id": 5, "name": "Bolsa"}]
            if method == "POST" and path == "stock/shoppinglist/add-product":
                self.assertEqual(body, {"product_id": 7, "qu_id": 5,
                                        "list_id": 1, "product_amount": 1.5})
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        self.assertEqual(barcode_stock.add_to_shopping_list(7, "3", "5"), "Tomate")
        with self.assertRaises(barcode_stock.BarcodeError):
            barcode_stock.add_to_shopping_list(7, "1.555", "4")
        with self.assertRaises(barcode_stock.BarcodeError):
            barcode_stock.add_to_shopping_list(7, "2", "999")
        self.assertEqual(sum(x.args[0] == "POST" for x in api.call_args_list), 1)

    @patch("barcode_stock.grocy")
    def test_shopping_list_done_and_remove_only_default_list(self, api):
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/shopping_list/9":
                return {"id": 9, "shopping_list_id": 1, "done": 0}
            if method == "GET" and path == "objects/shopping_list/10":
                return {"id": 10, "shopping_list_id": 2}
            if method in ("PUT", "DELETE"):
                self.assertEqual(path, "objects/shopping_list/9")
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        barcode_stock.update_shopping_list_item(9, True)
        barcode_stock.remove_shopping_list_item(9)
        with self.assertRaises(barcode_stock.BarcodeError):
            barcode_stock.remove_shopping_list_item(10)

    @patch("barcode_stock.grocy")
    def test_changing_stock_unit_with_existing_stock_is_blocked(self, api):
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/products/7":
                return {"id": 7, "name": "Tomate", "qu_id_stock": 2}
            if method == "GET" and path == "objects/quantity_units":
                return [{"id": 2, "name": "Piece"}, {"id": 4, "name": "Kilogram"}]
            if method == "GET" and path == "stock/products/7":
                return {"stock_amount": 3}
            raise AssertionError((method, path))
        api.side_effect = fake
        with self.assertRaises(barcode_stock.BarcodeError):
            barcode_stock.update_product_info(7, "Tomate", "1", "4")
        self.assertFalse(any(c.args[0] == "PUT" for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_changing_stock_unit_with_zero_stock(self, api):
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/products/7":
                return {"id": 7, "name": "Tomate", "qu_id_stock": 2}
            if method == "GET" and path == "objects/quantity_units":
                return [{"id": 2}, {"id": 4}]
            if method == "GET" and path == "stock/products/7":
                return {"stock_amount": 0}
            if method == "PUT" and path == "objects/products/7":
                self.assertEqual(body["qu_id_stock"], 4)
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        barcode_stock.update_product_info(7, "Tomate", "1", "4")

    @patch("barcode_stock.grocy")
    def test_stock_adjustment_requires_confirmation_and_two_decimals(self, api):
        api.side_effect = lambda method, path, body=None: (
            {"stock_amount": "1.25"} if method == "GET" and path == "stock/products/7"
            else {})
        preview = barcode_stock.prepare_stock_adjustment(7, "2,50", "1.25")
        self.assertEqual(preview["difference"], "1.25")
        self.assertEqual(api.call_count, 1)
        with self.assertRaises(barcode_stock.BarcodeError):
            barcode_stock.prepare_stock_adjustment(7, "2.555", "1.25")
        self.assertEqual(api.call_count, 1)
        result = barcode_stock.apply_stock_adjustment(preview)
        self.assertEqual(result["after"], "2.50")
        self.assertTrue(any(c.args[0] == "POST" and c.args[1] == "stock/products/7/add"
                            for c in api.call_args_list))

    @patch("barcode_stock.grocy")
    def test_association_on_product_sheet_never_changes_stock(self, api):
        def fake(method, path, body=None):
            if method == "GET" and path == "objects/products/7":
                return {"id": 7, "name": "Tomate"}
            if method == "GET" and path == "objects/product_barcodes":
                return []
            if method == "POST" and path == "objects/product_barcodes":
                self.assertEqual(body, {"product_id": 7, "barcode": "1234567890123"})
                return {}
            raise AssertionError((method, path))
        api.side_effect = fake
        result = barcode_stock.associate_product_barcode(7, "1234567890123")
        self.assertFalse(result["already_linked"])

    def test_reject_non_numeric_barcodes(self):
        with self.assertRaises(barcode_stock.BarcodeError):
            barcode_stock.validate_barcode("abc")

class PhotoTests(unittest.TestCase):
    def test_reject_unsafe_image_url(self):
        self.assertIsNone(product_images.safe_image_url("http://images.openfoodfacts.org/x.jpg"))
        self.assertIsNone(product_images.safe_image_url("https://evil.example/x.jpg"))
        self.assertIsNone(product_images.safe_image_url("https://images.openfoodfacts.org.evil.example/x.jpg"))

    @patch("product_images.urllib.request.urlopen")
    def test_exact_barcode_image_lookup(self, open_url):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({"status": 1, "product": {
            "code": "1234567890123", "product_name": "Leche",
            "image_front_small_url": "https://images.openfoodfacts.org/images/x.jpg"}}).encode()
        open_url.return_value = response
        result = product_images.lookup_image("1234567890123")
        self.assertEqual(result["name"], "Leche")

    @patch("product_images.urllib.request.urlopen")
    def test_barcode_mismatch_returns_none(self, open_url):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({"status": 1, "product": {
            "code": "0000000000000", "image_front_url": "https://images.openfoodfacts.org/x.jpg"}}).encode()
        open_url.return_value = response
        self.assertIsNone(product_images.lookup_image("1234567890123"))

if __name__ == "__main__":
    unittest.main()
