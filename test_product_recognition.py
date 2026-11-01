"""Explicit full-frame vision requests: privacy, structured output and no writes."""

import base64
import io
import json
import os
import unittest
from unittest.mock import patch
from PIL import Image
import product_recognition as vision
import web


def picture():
    output = io.BytesIO()
    image = Image.new("RGB", (1200, 600), "red")
    exif = Image.Exif()
    exif[270] = "private image metadata"
    image.save(output, "JPEG", exif=exif)
    return output.getvalue()


class RecognitionTests(unittest.TestCase):
    def setUp(self):
        secret = patch.dict(web.app.config, {"SECRET_KEY": "disposable-photo-test"})
        secret.start()
        self.addCleanup(secret.stop)
        self.client = web.app.test_client()
        self.ingress = patch.object(web, "INGRESS_MODE", True)
        self.ingress.start()
        self.addCleanup(self.ingress.stop)
        self.token = self.client.get("/api/v1/auth/status").json["csrf_token"]
        self.headers = {"X-CSRF-Token": self.token}
        self.suggestion = {
            "name": "Yogur natural",
            "brand": "Example",
            "size_text": "6 x 125 g",
            "confidence": "medium",
            "visible_barcode": "",
        }

    def api_response(self, result):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, *_):
                return json.dumps(result).encode()

        return Response()

    def analyze(self, **changes):
        result = {
            "status": "completed",
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": json.dumps({**self.suggestion, **changes})}
                    ]
                }
            ],
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "disposable-not-a-real-key"}), patch.object(
            vision.urllib.request, "urlopen", return_value=self.api_response(result)
        ) as remote:
            value = vision.identify(picture(), "8412345678901")
        return value, remote.call_args.args[0]

    def test_complete_sanitized_frame_is_sent_not_just_the_code(self):
        result, request = self.analyze()
        payload = json.loads(request.data)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        image_part = payload["input"][0]["content"][1]
        self.assertEqual(image_part["type"], "input_image")
        raw = base64.b64decode(image_part["image_url"].split(",")[1])
        with Image.open(io.BytesIO(raw)) as image:
            self.assertEqual(image.size, (1200, 600))
            self.assertEqual(len(image.getexif()), 0)
        self.assertEqual(result["barcode"], "8412345678901")
        self.assertTrue(result["advisory"])

    def test_ai_cannot_change_the_scanned_barcode_or_return_unbounded_fields(self):
        for changes in (
            {"visible_barcode": "12345678"},
            {"name": "x" * 201},
            {"confidence": "certain"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.analyze(**changes)

    def test_invalid_or_oversized_image_never_calls_provider(self):
        for data in (b"not an image", b"x" * (8 * 1024 * 1024 + 1)):
            with patch.object(vision.urllib.request, "urlopen") as remote, self.assertRaises(
                ValueError
            ):
                vision.identify(data, "8412345678901")
            remote.assert_not_called()

    def test_explicit_consent_csrf_and_valid_code_are_required(self):
        with patch.object(vision, "identify") as identify:
            self.assertEqual(self.client.post("/api/v1/photos/identify").status_code, 403)
            for fields in ({"barcode": "8412345678901"}, {"barcode": "bad", "consent": "true"}):
                response = self.client.post(
                    "/api/v1/photos/identify",
                    headers=self.headers,
                    data={**fields, "photo": (io.BytesIO(picture()), "photo.jpg")},
                )
                self.assertEqual(response.status_code, 400)
            identify.assert_not_called()

    def test_explicit_analysis_returns_suggestion_without_catalog_stock_or_photo_mutation(self):
        with patch.object(
            vision,
            "identify",
            return_value={**self.suggestion, "barcode": "8412345678901", "advisory": True},
        ) as identify, patch.object(web.barcode_stock, "grocy") as grocy, patch.object(
            web, "PHOTO_DIR"
        ) as directory:
            response = self.client.post(
                "/api/v1/photos/identify",
                headers=self.headers,
                data={
                    "consent": "true",
                    "barcode": "8412345678901",
                    "photo": (io.BytesIO(picture()), "photo.jpg"),
                },
            )
        self.assertEqual(response.status_code, 200, response.json)
        identify.assert_called_once()
        grocy.assert_not_called()
        directory.assert_not_called()

    def test_provider_error_is_sanitized_and_not_automatically_retried(self):
        with patch.object(
            vision, "identify", side_effect=ConnectionError("private provider response and API key")
        ) as identify:
            response = self.client.post(
                "/api/v1/photos/identify",
                headers=self.headers,
                data={
                    "consent": "true",
                    "barcode": "8412345678901",
                    "photo": (io.BytesIO(picture()), "photo.jpg"),
                },
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("API key", response.json["error"])
        identify.assert_called_once()
