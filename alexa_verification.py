"""Verify Alexa SHA-256 signatures against system-trusted certificate chains."""

import base64
import datetime as dt
import json
import re
import ssl
import urllib.request
from urllib.parse import urlsplit
from OpenSSL import crypto
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class InvalidAlexaRequest(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise InvalidAlexaRequest("Certificate redirects are not accepted")


def certificate_url(value):
    if not isinstance(value, str) or len(value) > 1024:
        raise InvalidAlexaRequest("Invalid certificate URL")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise InvalidAlexaRequest("Invalid certificate URL") from None
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname != "s3.amazonaws.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or port not in (None, 443)
        or not re.fullmatch(r"/echo\.api/[A-Za-z0-9_./-]+\.pem", parsed.path)
        or any(part in ("", ".", "..") for part in parsed.path.split("/")[2:])
    ):
        raise InvalidAlexaRequest("Invalid certificate URL")
    return value


def download_chain(url):
    url = certificate_url(url)
    with urllib.request.build_opener(NoRedirect()).open(url, timeout=2) as response:
        if response.geturl() != url:
            raise InvalidAlexaRequest("Unexpected certificate origin")
        content = response.read(65537)
    if len(content) > 65536:
        raise InvalidAlexaRequest("Certificate chain too large")
    return content


def trust_store():
    store = crypto.X509Store()
    for raw in ssl.create_default_context().get_ca_certs(binary_form=True):
        store.add_cert(crypto.load_certificate(crypto.FILETYPE_ASN1, raw))
    return store


def verify(raw, headers, skill_id, user_id):
    """Validate transport proof before trusting request fields or reading stock."""
    if not raw or len(raw) > 65536:
        raise InvalidAlexaRequest("Invalid request size")
    url = certificate_url(headers.get("SignatureCertChainUrl"))
    signature = headers.get("Signature-256", "")
    if not signature or len(signature) > 2048:
        raise InvalidAlexaRequest("Missing signature")
    try:
        signature = base64.b64decode(signature, validate=True)
        chain = x509.load_pem_x509_certificates(download_chain(url))
        if not chain or len(chain) > 8:
            raise InvalidAlexaRequest("Invalid certificate chain")
        leaf = chain[0]
        crypto.X509StoreContext(
            trust_store(),
            crypto.X509.from_cryptography(leaf),
            [crypto.X509.from_cryptography(cert) for cert in chain[1:]],
        ).verify_certificate()
        names = leaf.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value.get_values_for_type(x509.DNSName)
        if "echo-api.amazon.com" not in names:
            raise InvalidAlexaRequest("Wrong signing identity")
        public_key = leaf.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size < 2048:
            raise InvalidAlexaRequest("Unsupported signing key")
        public_key.verify(signature, raw, padding.PKCS1v15(), hashes.SHA256())
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("version") != "1.0":
            raise InvalidAlexaRequest("Invalid request envelope")
        request = payload["request"]
        timestamp = dt.datetime.fromisoformat(request["timestamp"].replace("Z", "+00:00"))
        if (
            timestamp.tzinfo is None
            or abs((dt.datetime.now(dt.timezone.utc) - timestamp).total_seconds()) > 150
        ):
            raise InvalidAlexaRequest("Expired request")
        system = payload.get("context", {}).get("System", {})
        session = payload.get("session", {})
        application = system.get("application") or session.get("application") or {}
        user = system.get("user") or session.get("user") or {}
        if application.get("applicationId") != skill_id or user.get("userId") != user_id:
            raise InvalidAlexaRequest("Unrecognized skill or user")
        # Reject conflicting signed identity copies as well.
        for container in (system, session):
            if (
                container.get("application")
                and container["application"].get("applicationId") != skill_id
            ):
                raise InvalidAlexaRequest("Conflicting skill identity")
            if container.get("user") and container["user"].get("userId") != user_id:
                raise InvalidAlexaRequest("Conflicting user identity")
        if (
            not isinstance(request.get("requestId"), str)
            or not 1 <= len(request["requestId"]) <= 300
        ):
            raise InvalidAlexaRequest("Missing request identity")
        return payload
    except InvalidAlexaRequest:
        raise
    except Exception:
        raise InvalidAlexaRequest("Alexa request verification failed") from None
