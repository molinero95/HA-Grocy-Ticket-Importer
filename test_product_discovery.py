"""Paid search is mocked; only cited, catalog-confirmed, checksum-valid GTINs survive."""
import io
import json
import os
import unittest
from unittest.mock import patch
import product_recognition as recognition
import product_images
with patch.dict(os.environ, {"WEB_PASSWORD": "test-password", "WEB_SESSION_SECRET": "test-secret-key"}):
    import web
import api_photos
from test_product_recognition import picture

CODE = "4006000082295"
OTHER = "3017620422003"
PAGE = "https://world.openbeautyfacts.org/product/" + CODE + "/example"
IMAGE = "https://images.openbeautyfacts.org/images/products/example.jpg"
CANDIDATE = {"barcode": CODE, "name": "Crema Example 100 ml", "image_url": IMAGE,
             "source_url": PAGE, "attribution": "Datos: Open Beauty Facts", "search_source_url": PAGE}


class DiscoveryTests(unittest.TestCase):
    def result(self, urls=None, sources=None, status="completed"):
        urls = urls if urls is not None else [PAGE]
        return {"status": status, "output": [
            {"type": "web_search_call", "status": "completed", "action": {
                "sources": [{"type": "url", "url": url} for url in (sources if sources is not None else urls)]}},
            {"type": "message", "content": [{"type": "output_text", "text": "Product matches",
                "annotations": [{"type": "url_citation", "url": url} for url in urls]}]},
        ]}

    def search(self, result=None, code="", found=CANDIDATE, failure=None):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(result or self.result()).encode()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "disposable-key"}), patch.object(
            recognition.urllib.request, "urlopen", return_value=response
        ) as remote, patch.object(product_images, "verify_discovered_product", return_value=found, side_effect=failure) as verify:
            output = recognition.discover("Crema Example 100 ml", code)
        return output, json.loads(remote.call_args.args[0].data), verify

    def test_search_requires_real_sources_and_verifies_before_returning(self):
        output, payload, verify = self.search()
        self.assertEqual(output["candidates"], [CANDIDATE])
        self.assertFalse(payload["store"])
        self.assertEqual(payload["tools"][0]["type"], "web_search")
        self.assertEqual(payload["tool_choice"], "required")
        self.assertIn("web_search_call.action.sources", payload["include"])
        self.assertIn("openbeautyfacts.org", payload["tools"][0]["filters"]["allowed_domains"])
        verify.assert_called_once_with(PAGE)

    def test_invented_unsafe_uncited_invalid_and_wrong_scanned_codes_are_not_looked_up(self):
        for urls, sources, code in (
            ([PAGE], [], ""),
            (["https://evil.invalid/product/" + CODE], None, ""),
            (["http://127.0.0.1/product/" + CODE], None, ""),
            (["https://world.openbeautyfacts.org.evil.invalid/product/" + CODE], None, ""),
            (["https://user:pass@world.openbeautyfacts.org/product/" + CODE], None, ""),
            (["https://world.openbeautyfacts.org/product/4006000082291"], None, ""),
            ([PAGE], None, OTHER),
        ):
            with self.subTest(urls=urls):
                output, _, verify = self.search(self.result(urls, sources), code)
                self.assertEqual(output["candidates"], [])
                verify.assert_not_called()

    def test_missing_catalog_match_is_not_treated_as_verified(self):
        output, _, verify = self.search(found=None)
        self.assertEqual(output["candidates"], [])
        verify.assert_called_once()

    def test_duplicate_citations_only_fetch_once_and_a_failed_catalog_is_advisory(self):
        output, _, verify = self.search(self.result([PAGE, PAGE]))
        self.assertEqual(len(output["candidates"]), 1)
        verify.assert_called_once()
        output, _, _ = self.search(failure=OSError("unavailable"))
        self.assertEqual(output["candidates"], [])

    def test_exact_api_lookup_uses_only_constructed_trusted_url_not_cited_url(self):
        with patch.object(product_images, "_fetch_catalog", return_value={k: v for k, v in CANDIDATE.items() if k != "search_source_url"}) as fetch:
            found = product_images.verify_discovered_product(PAGE + "?utm_source=chatgpt.com")
        self.assertEqual(found["barcode"], CODE)
        self.assertTrue(fetch.call_args.args[0].startswith("https://world.openbeautyfacts.org/api/v2/product/" + CODE + "?fields="))
        self.assertNotIn("utm_source", fetch.call_args.args[0])

    def test_invalid_query_and_incomplete_search_do_not_produce_a_candidate(self):
        for name in (None, "", "ab", "x" * 201):
            with self.subTest(name=name), patch.object(recognition.urllib.request, "urlopen") as remote, self.assertRaises(ValueError):
                recognition.discover(name)
            remote.assert_not_called()
        with self.assertRaises(ValueError):
            self.search(self.result(status="incomplete"))


    def test_standard_gtin_lengths_and_at_most_three_unique_lookups(self):
        codes = ["96385074", "036000291452", "09506000134352", CODE]
        urls = ["https://es.openfoodfacts.org/producto/" + code for code in codes]
        for code, url in zip(codes, urls):
            self.assertEqual(product_images.catalog_reference(url)[1], code)
        _, _, verify = self.search(self.result(urls))
        self.assertEqual(verify.call_count, 3)

    def test_oversized_search_response_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "demasiado grande"):
            self.search({"status": "completed", "output": [], "extra": "x" * 65537})

    def test_photo_visible_code_without_prior_code_remains_only_a_suggestion(self):
        response = unittest.mock.MagicMock()
        suggestion = {"name": "Crema Example", "brand": "Example", "size_text": "100 ml",
                      "confidence": "medium", "visible_barcode": CODE}
        response.__enter__.return_value.read.return_value = json.dumps({"status": "completed", "output": [
            {"content": [{"type": "output_text", "text": json.dumps(suggestion)}]}]}).encode()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "disposable-key"}), patch.object(
            recognition.urllib.request, "urlopen", return_value=response
        ):
            found = recognition.identify(picture())
        self.assertEqual(found["barcode"], "")
        self.assertEqual(found["visible_barcode"], CODE)
        self.assertTrue(found["advisory"])


class DiscoveryApiTests(unittest.TestCase):
    def setUp(self):
        ingress = patch.object(web, "INGRESS_MODE", True)
        ingress.start()
        self.addCleanup(ingress.stop)
        secret = patch.dict(web.app.config, {"SECRET_KEY": "disposable-discovery-secret"})
        secret.start()
        self.addCleanup(secret.stop)
        self.client = web.app.test_client()
        self.headers = {"X-CSRF-Token": self.client.get("/api/v1/auth/status").json["csrf_token"]}

    def test_consent_csrf_and_bounded_query_are_required_before_provider(self):
        payload = {"name": "Crema Example 100 ml", "consent": True}
        with patch.object(recognition, "discover") as discover:
            self.assertEqual(self.client.post("/api/v1/photos/discover", json=payload).status_code, 403)
            for change in ({"consent": False}, {"name": "a"}, {"name": 4}, {"name": "x" * 201}, {"barcode": "bad"}, {"barcode": 12}):
                self.assertEqual(self.client.post("/api/v1/photos/discover", json={**payload, **change}, headers=self.headers).status_code, 400)
            discover.assert_not_called()

    def test_search_is_read_only_and_anonymous_access_is_rejected(self):
        with patch.object(recognition, "discover", return_value={"candidates": [CANDIDATE], "advisory": True}) as discover, patch.object(web.barcode_stock, "grocy") as grocy:
            response = self.client.post("/api/v1/photos/discover", headers=self.headers, json={"name": "Crema Example", "consent": True})
            self.assertEqual(response.status_code, 200)
            discover.assert_called_once_with("Crema Example", "")
            grocy.assert_not_called()
            with patch.object(web, "INGRESS_MODE", False), patch.dict(os.environ, {"WEB_PASSWORD": "test-password"}):
                other = web.app.test_client()
                self.assertEqual(other.post("/api/v1/photos/discover", json={"name": "Crema Example", "consent": True}).status_code, 403)
                token = other.get("/api/v1/auth/status").json["csrf_token"]
                self.assertEqual(other.post("/api/v1/photos/discover", headers={"X-CSRF-Token": token}, json={"name": "Crema Example", "consent": True}).status_code, 401)

    def test_busy_and_provider_errors_do_not_leak_or_retry(self):
        payload = {"name": "Crema Example", "consent": True}
        with patch.object(recognition, "discover", side_effect=RuntimeError("private provider key")) as discover:
            response = self.client.post("/api/v1/photos/discover", json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("private", response.json["error"])
            discover.assert_called_once()
            api_photos.IDENTIFY_LOCK.acquire()
            try:
                self.assertEqual(self.client.post("/api/v1/photos/discover", json=payload, headers=self.headers).status_code, 409)
            finally:
                api_photos.IDENTIFY_LOCK.release()
            discover.assert_called_once()

    def test_photo_can_be_identified_without_barcode_without_assigning_visible_code(self):
        with patch.object(recognition, "identify", return_value={"name": "Crema Example", "visible_barcode": CODE, "barcode": "", "advisory": True}) as identify:
            response = self.client.post("/api/v1/photos/identify", headers=self.headers, data={"consent": "true", "photo": (io.BytesIO(picture()), "front.jpg")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(identify.call_args.args[1], "")
        self.assertEqual(response.json["suggestion"]["barcode"], "")
