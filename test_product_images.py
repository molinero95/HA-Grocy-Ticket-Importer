"""Exact-code cosmetics lookup, trusted hosts and useful partial catalog data."""
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import barcode_stock
import product_images

CODE = "4006000082295"
BEAUTY_IMAGE = "https://images.openbeautyfacts.org/images/products/400/600/008/2295/front_fr.3.400.jpg"


def response(product=None):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.read.return_value = json.dumps({"status": 1 if product else 0, "product": product or {}}).encode()
    return result


class ProductImageTests(unittest.TestCase):
    @patch("product_images.urllib.request.urlopen")
    def test_cosmetic_is_found_after_food_and_products_miss(self, lookup):
        lookup.side_effect = [HTTPError("https://example.test", 404, "not found", {}, None),
                              response(), response({"code": CODE, "product_name": "Nivea", "image_front_small_url": BEAUTY_IMAGE})]
        found = product_images.lookup_image(CODE)
        self.assertEqual(found["name"], "Nivea")
        self.assertEqual(found["image_url"], BEAUTY_IMAGE)
        self.assertEqual(found["source_url"], "https://world.openbeautyfacts.org/product/" + CODE)
        self.assertIn("world.openbeautyfacts.org/api/v2/product/" + CODE, lookup.call_args.args[0].full_url)

    @patch("product_images.urllib.request.urlopen")
    def test_404_from_every_catalog_means_missing_not_service_unavailable(self, lookup):
        lookup.side_effect = HTTPError("https://example.test", 404, "not found", {}, None)
        self.assertIsNone(product_images.lookup_image(CODE))
        self.assertEqual(lookup.call_count, len(product_images.SOURCES))

    @patch("product_images.urllib.request.urlopen")
    def test_name_only_does_not_prevent_finding_a_photo_in_another_catalog(self, lookup):
        lookup.side_effect = [response({"code": CODE, "product_name": "Nivea"}), response(),
                              response({"code": CODE, "product_name": "Q10", "image_front_url": BEAUTY_IMAGE})]
        self.assertEqual(product_images.lookup_image(CODE)["image_url"], BEAUTY_IMAGE)

    @patch("product_images.urllib.request.urlopen")
    def test_name_only_result_survives_other_catalog_outages(self, lookup):
        lookup.side_effect = [response({"code": CODE, "product_name": "Nivea", "product_name_es": "Loción corporal"}),
                              TimeoutError(), TimeoutError()]
        found = product_images.lookup_image(CODE)
        self.assertEqual(found["name"], "Loción corporal")
        self.assertIsNone(found["image_url"])

    @patch("product_images.urllib.request.urlopen")
    def test_complete_catalog_outage_still_reports_unavailability(self, lookup):
        lookup.side_effect = TimeoutError()
        with self.assertRaises(ConnectionError):
            product_images.lookup_image(CODE)

    @patch("product_images.urllib.request.urlopen")
    def test_wrong_cosmetics_code_is_not_accepted(self, lookup):
        lookup.side_effect = [response(), response(), response({"code": "12345678", "product_name": "Wrong cream", "image_front_url": BEAUTY_IMAGE})]
        self.assertIsNone(product_images.lookup_image(CODE))

    def test_beauty_host_validation_rejects_credentials_ports_and_impostors(self):
        self.assertEqual(product_images.safe_image_url(BEAUTY_IMAGE), BEAUTY_IMAGE)
        for url in ["http://images.openbeautyfacts.org/a.jpg", "https://images.openbeautyfacts.org.evil.test/a.jpg",
                    "https://user@images.openbeautyfacts.org/a.jpg", "https://images.openbeautyfacts.org:invalid/a.jpg",
                    "https://images.openbeautyfacts.org:8443/a.jpg"]:
            with self.subTest(url=url):
                self.assertIsNone(product_images.safe_image_url(url))

    @patch("barcode_stock.grocy")
    def test_beauty_photo_round_trip_preserves_existing_product_notes(self, grocy):
        grocy.return_value = {"id": 7, "name": "Crema", "description": "Notas del producto"}
        barcode_stock.save_product_photo(7, BEAUTY_IMAGE)
        method, endpoint, payload = grocy.call_args.args
        self.assertEqual((method, endpoint), ("PUT", "objects/products/7"))
        self.assertEqual(set(payload), {"description"})
        self.assertTrue(payload["description"].startswith("Notas del producto\n"))
        self.assertEqual(barcode_stock.saved_photo(payload), BEAUTY_IMAGE)


if __name__ == "__main__":
    unittest.main()
