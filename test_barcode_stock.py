"""Barcode and photo tests. No real Grocy writes or network calls."""
import json
import unittest
from unittest.mock import Mock, patch

import barcode_stock
import product_images

PRODUCTS = [{"id": 5, "name": "Leche", "qu_id_stock": 2},
            {"id": 8, "name": "Pasta", "qu_id_stock": 2}]

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
