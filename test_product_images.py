"""Universal catalog routing, direct fallbacks and exact-code metadata guards."""
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import barcode_stock
import product_images

CODE = "4006000082295"
BEAUTY_HOST = "world.openbeautyfacts.org"
BEAUTY_IMAGE = "https://images.openbeautyfacts.org/images/products/400/600/008/2295/front_fr.3.400.jpg"


def response(product=None, *, status=None, host="world.openfoodfacts.org"):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.geturl.return_value = "https://" + host + "/api/v3/product/" + CODE
    result.read.return_value = json.dumps({"status": status if status is not None else (1 if product else 0),
                                         "product": product or {}}).encode()
    return result


def cream(**fields):
    return {"code": CODE, "product_name": "Nivea", "product_type": "beauty",
            "image_front_small_url": BEAUTY_IMAGE, **fields}


class ProductImageTests(unittest.TestCase):
    def setUp(self):
        factory = patch("product_images.urllib.request.build_opener")
        self.open = factory.start().return_value.open
        self.addCleanup(factory.stop)
        self.open.return_value = response()

    def test_universal_beauty_redirect_returns_photo_without_direct_queries(self):
        self.open.return_value = response(cream(), status="success", host=BEAUTY_HOST)
        found = product_images.lookup_image(CODE)
        self.assertEqual(found["name"], "Nivea")
        self.assertEqual(found["image_url"], BEAUTY_IMAGE)
        self.assertEqual(found["source_url"], "https://world.openbeautyfacts.org/product/" + CODE)
        self.assertEqual(found["attribution"], "Datos: Open Beauty Facts")
        self.assertEqual(self.open.call_count, 1)
        req = self.open.call_args.args[0]
        self.assertIn("/api/v3/product/" + CODE + "?product_type=all", req.full_url)
        self.assertIn("product_type,product_name", req.full_url)
        self.assertIn("Despensa/1.3.0", req.get_header("User-agent"))
        self.assertEqual(self.open.call_args.kwargs["timeout"], 8)

    def test_universal_food_and_general_products_keep_their_source(self):
        for kind, host, source in [("food", "world.openfoodfacts.org", "Open Food Facts"),
                                   ("product", "world.openproductsfacts.org", "Open Products Facts")]:
            with self.subTest(kind=kind):
                self.open.return_value = response(cream(product_type=kind), status="success", host=host)
                found = product_images.lookup_image(CODE)
                self.assertEqual(found["attribution"], "Datos: " + source)
                self.assertEqual(found["source_url"], "https://" + host + "/product/" + CODE)

    def test_cosmetic_direct_fallback_survives_universal_outage(self):
        self.open.side_effect = [TimeoutError(), HTTPError("https://example.test", 404, "not found", {}, None),
                                 response(), response(cream(), host=BEAUTY_HOST)]
        found = product_images.lookup_image(CODE)
        self.assertEqual(found["image_url"], BEAUTY_IMAGE)
        self.assertIn("world.openbeautyfacts.org/api/v2/product/" + CODE, self.open.call_args.args[0].full_url)
        self.assertEqual(self.open.call_count, 4)

    def test_universal_404_means_missing_without_extra_catalog_requests(self):
        self.open.side_effect = HTTPError("https://example.test", 404, "not found", {}, None)
        self.assertIsNone(product_images.lookup_image(CODE))
        self.assertEqual(self.open.call_count, 1)

    def test_direct_404s_after_universal_failure_are_not_a_total_outage(self):
        self.open.side_effect = [TimeoutError()] + [HTTPError("https://example.test", 404, "not found", {}, None)] * 3
        self.assertIsNone(product_images.lookup_image(CODE))

    def test_name_only_does_not_prevent_finding_a_photo_in_another_catalog(self):
        self.open.side_effect = [response(cream(image_front_small_url=None), status="success", host=BEAUTY_HOST),
                                 response(), response(), response(cream(product_name="Q10"), host=BEAUTY_HOST)]
        self.assertEqual(product_images.lookup_image(CODE)["image_url"], BEAUTY_IMAGE)

    def test_name_only_result_survives_other_catalog_outages(self):
        self.open.side_effect = [response(cream(image_front_small_url=None, product_name_es="Loción corporal"),
                                         status="success", host=BEAUTY_HOST), TimeoutError(), TimeoutError(), TimeoutError()]
        found = product_images.lookup_image(CODE)
        self.assertEqual(found["name"], "Loción corporal")
        self.assertIsNone(found["image_url"])

    def test_complete_catalog_outage_still_reports_unavailability(self):
        self.open.side_effect = TimeoutError()
        with self.assertRaises(ConnectionError):
            product_images.lookup_image(CODE)
        self.assertEqual(self.open.call_count, 4)

    def test_wrong_code_is_not_accepted_from_universal_or_direct_catalogs(self):
        self.open.return_value = response(cream(code="12345678"), status="success", host=BEAUTY_HOST)
        self.assertIsNone(product_images.lookup_image(CODE))

    def test_malformed_universal_json_falls_back_to_a_direct_source(self):
        broken = response()
        broken.read.return_value = b"<html>Gateway error</html>"
        self.open.side_effect = [broken, response(cream(), host=BEAUTY_HOST)]
        self.assertEqual(product_images.lookup_image(CODE)["image_url"], BEAUTY_IMAGE)

    def test_failed_status_and_unsupported_product_types_are_not_used(self):
        for payload in [response(cream(), status="failure"), response(cream(product_type="petfood"), status="success"),
                        response(cream(product_type=["beauty"]), status="success")]:
            with self.subTest(payload=payload):
                self.open.return_value = payload
                self.assertIsNone(product_images.lookup_image(CODE))

    def test_success_with_errors_keeps_valid_exact_product_metadata(self):
        self.open.return_value = response(cream(), status="success_with_errors", host=BEAUTY_HOST)
        self.assertEqual(product_images.lookup_image(CODE)["image_url"], BEAUTY_IMAGE)

    def test_untrusted_final_source_cannot_supply_product_metadata(self):
        self.open.side_effect = [response(cream(), status="success", host="evil.test"), response(), response(), response()]
        self.assertIsNone(product_images.lookup_image(CODE))

    def test_redirects_only_follow_the_three_supported_https_catalogs(self):
        handler = product_images._CatalogRedirectHandler()
        req = Request(product_images.UNIVERSAL_API + CODE)
        for host in product_images.CATALOGS:
            url = "https://" + host + "/api/v3/product/" + CODE
            self.assertEqual(handler.redirect_request(req, None, 302, "Found", {}, url).full_url, url)
        for url in ["http://world.openbeautyfacts.org/a", "https://world.openbeautyfacts.org.evil.test/a",
                    "https://user@world.openbeautyfacts.org/a", "https://world.openbeautyfacts.org:invalid/a",
                    "https://world.openbeautyfacts.org:8443/a", "https://world.openpetfoodfacts.org/a", "http://127.0.0.1/a"]:
            with self.subTest(url=url), self.assertRaises(URLError):
                handler.redirect_request(req, None, 302, "Found", {}, url)

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
