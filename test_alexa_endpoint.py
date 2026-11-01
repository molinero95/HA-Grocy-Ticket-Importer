"""Signed requests exercise the isolated voice listener with a disposable CA."""

import base64
import datetime as dt
import json
import os
import unittest
from unittest.mock import patch
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from OpenSSL import crypto
import alexa_endpoint as voice
import alexa_verification as verification

SKILL = "amzn1.ask.skill.disposable-test"
USER = "amzn1.ask.account.disposable-test"


class AlexaEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Disposable test CA")])
        now = dt.datetime.now(dt.timezone.utc)
        cls.root = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(cls.root_key.public_key())
            .serial_number(1)
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
            .sign(cls.root_key, hashes.SHA256())
        )

    def leaf(self, host="echo-api.amazon.com", expired=False):
        now = dt.datetime.now(dt.timezone.utc)
        return (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
            .issuer_name(self.root.subject)
            .public_key(self.key.public_key())
            .serial_number(2)
            .not_valid_before(now - dt.timedelta(days=2))
            .not_valid_after(now + dt.timedelta(days=-1 if expired else 1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(self.root_key, hashes.SHA256())
        )

    def setUp(self):
        self.client = voice.app.test_client()
        env = patch.dict(
            os.environ,
            {"ALEXA_SKILL_ENABLED": "1", "ALEXA_SKILL_ID": SKILL, "ALEXA_SKILL_USER_ID": USER},
        )
        env.start()
        self.addCleanup(env.stop)
        self.payload = {
            "version": "1.0",
            "context": {
                "System": {"application": {"applicationId": SKILL}, "user": {"userId": USER}}
            },
            "request": {
                "type": "IntentRequest",
                "locale": "es-ES",
                "requestId": "disposable-request",
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "intent": {"name": "GetStockIntent", "slots": {"Product": {"value": "Leche"}}},
            },
        }
        self.rows = [
            {"id": 7, "name": "Leche entera", "amount": "4", "unit": "Piece"},
            {"id": 8, "name": "Arroz", "amount": "1.5", "unit": "Kilogram"},
        ]
        snapshot = patch.object(voice.barcode_stock, "inventory_snapshot", return_value=self.rows)
        self.snapshot = snapshot.start()
        self.addCleanup(snapshot.stop)
        meta = patch.object(
            voice, "local_metadata", return_value=([{"name": "Leche", "product_id": 7}], {})
        )
        meta.start()
        self.addCleanup(meta.stop)
        self.store = crypto.X509Store()
        self.store.add_cert(crypto.X509.from_cryptography(self.root))
        trust = patch.object(verification, "trust_store", return_value=self.store)
        trust.start()
        self.addCleanup(trust.stop)
        self.download = patch.object(
            verification,
            "download_chain",
            return_value=self.leaf().public_bytes(serialization.Encoding.PEM),
        )
        self.download_mock = self.download.start()
        self.addCleanup(self.download.stop)

    def send(self, raw=None, **headers):
        data = json.dumps(self.payload).encode()
        signed = base64.b64encode(self.key.sign(data, padding.PKCS1v15(), hashes.SHA256())).decode()
        return self.client.post(
            "/alexa/despensa",
            data=raw if raw is not None else data,
            content_type="application/json",
            headers={
                "SignatureCertChainUrl": "https://s3.amazonaws.com/echo.api/test.pem",
                "Signature-256": signed,
                **headers,
            },
        )

    def test_valid_signed_owner_reads_stock_and_no_panel_is_mounted(self):
        result = self.send()
        self.assertEqual(result.status_code, 200, result.json)
        self.assertIn("Leche entera: 4 unidades", result.json["response"]["outputSpeech"]["text"])
        self.assertEqual(result.headers["Cache-Control"], "no-store")
        for path in (
            "/",
            "/api/v1/inventory",
            "/api/v1/auth/status",
            "/api/v1/receipts",
            "/assets/x.js",
        ):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get("/alexa/despensa").status_code, 405)

    def test_tampered_body_and_missing_signature_never_read_stock(self):
        self.assertEqual(self.send(raw=b"{}").status_code, 400)
        self.assertEqual(self.send(**{"Signature-256": ""}).status_code, 400)
        self.snapshot.assert_not_called()

    def test_expired_future_and_naive_timestamps_are_rejected(self):
        for stamp in (
            (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=160)).isoformat(),
            (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=160)).isoformat(),
            "2026-11-01T01:00:00",
        ):
            self.payload["request"]["timestamp"] = stamp
            self.assertEqual(self.send().status_code, 400)
        self.snapshot.assert_not_called()

    def test_wrong_owner_skill_host_untrusted_root_and_expired_leaf_fail_closed(self):
        self.payload["context"]["System"]["user"]["userId"] = "other"
        self.assertEqual(self.send().status_code, 400)
        self.payload["context"]["System"]["user"]["userId"] = USER
        self.payload["context"]["System"]["application"]["applicationId"] = "other"
        self.assertEqual(self.send().status_code, 400)
        self.payload["context"]["System"]["application"]["applicationId"] = SKILL
        for cert in (self.leaf("attacker.test"), self.leaf(expired=True)):
            self.download_mock.return_value = cert.public_bytes(serialization.Encoding.PEM)
            self.assertEqual(self.send().status_code, 400)
        self.download_mock.return_value = self.leaf().public_bytes(serialization.Encoding.PEM)
        with patch.object(verification, "trust_store", return_value=crypto.X509Store()):
            self.assertEqual(self.send().status_code, 400)
        self.snapshot.assert_not_called()

    def test_certificate_url_is_validated_before_any_download(self):
        for url in (
            "http://s3.amazonaws.com/echo.api/x.pem",
            "https://evil.test/echo.api/x.pem",
            "https://s3.amazonaws.com:bad/echo.api/x.pem",
            "https://s3.amazonaws.com/echo.api/../private.pem",
            "https://s3.amazonaws.com/echo.api/%2fsecret.pem",
            "https://user@s3.amazonaws.com/echo.api/x.pem",
            "https://s3.amazonaws.com/echo.api/x.pem?redirect=evil",
        ):
            self.assertEqual(self.send(SignatureCertChainUrl=url).status_code, 400, url)
        self.download_mock.assert_not_called()
        self.snapshot.assert_not_called()
        with self.assertRaises(verification.InvalidAlexaRequest):
            verification.NoRedirect().redirect_request(None, None, None, None, None, None)

    def test_disabled_and_oversized_requests_do_not_verify_or_read(self):
        with patch.dict(os.environ, {"ALEXA_SKILL_ENABLED": "0"}):
            self.assertEqual(self.send().status_code, 503)
        self.assertEqual(self.send(raw=b"x" * 65537).status_code, 413)
        self.download_mock.assert_not_called()
        self.snapshot.assert_not_called()

    def test_ambiguous_products_require_clarification_and_missing_is_not_zero(self):
        self.rows.append({"id": 9, "name": "Leche desnatada", "amount": "1", "unit": "Piece"})
        with patch.object(voice, "local_metadata", return_value=([], {})):
            answer = self.send().json["response"]
            self.assertFalse(answer["shouldEndSession"])
            self.assertIn("varios productos", answer["outputSpeech"]["text"])
        self.payload["request"]["intent"]["slots"]["Product"]["value"] = "Never existed"
        self.assertIn("No encuentro", self.send().json["response"]["outputSpeech"]["text"])

    def test_low_stock_respects_thresholds_and_opt_out(self):
        self.payload["request"]["intent"] = {"name": "LowStockIntent"}
        with patch.object(
            voice,
            "local_metadata",
            return_value=([], {7: (voice.Decimal("4"), True), 8: (voice.Decimal("3"), False)}),
        ):
            text = self.send().json["response"]["outputSpeech"]["text"]
        self.assertIn("1 producto", text)
        self.assertIn("Leche entera", text)
        self.assertNotIn("Arroz", text)

    def test_upstream_failure_does_not_claim_zero_stock(self):
        self.snapshot.side_effect = ConnectionError("private URL and secret must not leak")
        text = self.send().json["response"]["outputSpeech"]["text"]
        self.assertIn("No puedo consultar", text)
        self.assertNotIn("secret", text)
