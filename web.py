#!/usr/bin/env python3
"""Despensa HTTP entrypoint: React, authenticated JSON APIs and basic fallback."""
import hmac
import html
import os
import re
import secrets
import subprocess
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template_string, request, session, url_for, send_file, send_from_directory
from werkzeug.exceptions import HTTPException

import extract
import barcode_stock
import product_images
import variant_catalog
import shopping_match_queue

ROOT = Path(__file__).resolve().parent
load_dotenv(os.environ.get("GROCY_ENV_FILE", str(ROOT / ".env")))
DATA = Path(os.environ.get("RECEIPT_DATA_DIR", str(ROOT / "runtime" / "receipts")))
ALLOWED = {".pdf", ".jpg", ".jpeg", ".png"}
PHOTO_DIR = Path(os.environ.get("PRODUCT_IMAGE_DIR", str(ROOT / "runtime" / "product_images")))
LOCK = threading.Lock()
INGRESS_MODE = os.environ.get("HA_INGRESS_MODE") == "1"


class IngressPrefixMiddleware:
    """The trusted HA proxy strips PATH_INFO and supplies the public prefix."""
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __call__(self, environ, start_response):
        prefix = environ.get("HTTP_X_INGRESS_PATH", "").rstrip("/")
        if INGRESS_MODE and prefix.startswith("/api/hassio_ingress/"):
            environ["SCRIPT_NAME"] = prefix
        return self.wrapped(environ, start_response)


app = Flask(__name__)
app.wsgi_app = IngressPrefixMiddleware(app.wsgi_app)
app.config.update(SECRET_KEY=os.environ.get("WEB_SESSION_SECRET", ""), MAX_CONTENT_LENGTH=12 * 1024 * 1024,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict")


def configured():
    return bool(app.secret_key and (INGRESS_MODE or os.environ.get("WEB_PASSWORD")))


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


@app.before_request
def protect():
    if not configured():
        abort(503)
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        token = session.get("csrf")
        supplied = request.headers.get("X-CSRF-Token", "") if request.path.startswith("/api/v1/") else request.form.get("csrf", "")
        if not token or not hmac.compare_digest(supplied.encode("utf-8"), token.encode("utf-8")):
            abort(403)
    public = {"index", "react_preview", "react_assets", "basic", "basic_login", "api_v1_auth_status", "api_v1_auth_login"}
    if request.endpoint not in public and not (INGRESS_MODE or session.get("auth")):
        abort(401)


@app.errorhandler(HTTPException)
def http_error(error):
    if request.path.startswith("/api/v1/"):
        messages = {401: "La sesión ha caducado. Vuelve a iniciar sesión.",
                    403: "No se pudo verificar la sesión. Actualiza la página antes de continuar.",
                    413: "El archivo supera el tamaño máximo permitido.",
                    503: "Despensa no está configurada o no está disponible."}
        return jsonify({"error": messages.get(error.code, error.name)}), error.code
    return error


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https://images.openfoodfacts.org https://images.openproductsfacts.org https://images.openbeautyfacts.org; "
        "media-src 'self' blob:; connect-src 'self'; base-uri 'self'; object-src 'none'; form-action 'self'; frame-ancestors 'self'")
    if request.path.startswith("/api/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def frontend_directory():
    return Path(os.environ.get("FRONTEND_DIST_DIR", str(ROOT / "frontend_dist")))


@app.get("/")
def index():
    path = frontend_directory() / "index.html"
    if not path.is_file():
        return "La interfaz no está compilada. Ejecuta npm run build en frontend y configura FRONTEND_DIST_DIR.", 503
    base = html.escape(url_for("index"), quote=True)
    fallback = html.escape(url_for("basic"), quote=True)
    page = path.read_text(encoding="utf-8").replace("<head>", f'<head><base href="{base}">', 1)
    page = page.replace("<body>", f'<body><noscript><p>Activa JavaScript o <a href="{fallback}">abre la vista básica</a>.</p></noscript>', 1)
    return app.response_class(page, mimetype="text/html", headers={"Cache-Control": "no-store"})


@app.get("/react/")
def react_preview():
    return index()


@app.get("/assets/<path:filename>")
def react_assets(filename):
    return send_from_directory(frontend_directory() / "assets", filename, max_age=31536000)


@app.get("/product/<int:product_id>/photo/local")
def local_product_photo(product_id):
    from api_photos import image_directory
    path = image_directory() / f"{product_id}.jpg"
    if not path.is_file():
        abort(404)
    response = send_file(path, mimetype="image/jpeg", max_age=3600)
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


# This deliberately small, script-free fallback keeps stock-unit shopping
# controls available without maintaining a second full application frontend.
BASIC = '''<!doctype html><html lang="es"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Despensa básica</title></head><body>
<h1>Despensa</h1><a href="{{ url_for('index') }}">Interfaz completa</a>
{% if error %}<p role="alert">{{ error }}</p>{% endif %}
{% if not authenticated %}<form method="post" action="{{ url_for('basic_login') }}"><input type="hidden" name="csrf" value="{{ csrf }}"><label>Contraseña<input type="password" name="password" autocomplete="current-password" required></label><button>Entrar</button></form>
{% else %}<h2>Mi despensa</h2><ul>{% for item in items %}<li><strong>{{ item.name }}</strong> · {{ item.amount }} {{ item.unit }} · En compra: {{ item.shopping_amount }} {{ item.shopping_unit }}
<form method="post" action="{{ url_for('basic_shopping_step', product_id=item.id) }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button name="direction" value="minus" {% if not item.shopping_can_subtract %}disabled{% endif %}>−</button><button name="direction" value="plus">Añadir {{ item.shopping_step }}</button></form></li>{% endfor %}</ul>{% endif %}</body></html>'''


@app.get("/basic")
def basic():
    authenticated = INGRESS_MODE or session.get("auth")
    items, error, status = [], "", 200
    if authenticated:
        try:
            items = barcode_stock.inventory_with_shopping()
        except Exception:
            error, status = "No se pudo cargar Grocy. No se ha modificado ningún producto.", 503
    return render_template_string(BASIC, authenticated=authenticated, csrf=csrf_token(), items=items, error=error), status


@app.post("/basic/login")
def basic_login():
    expected = os.environ.get("WEB_PASSWORD", "")
    if not expected or not hmac.compare_digest(request.form.get("password", "").encode("utf-8"), expected.encode("utf-8")):
        return render_template_string(BASIC, authenticated=False, csrf=csrf_token(), error="Contraseña incorrecta"), 401
    session.clear()
    session["auth"] = True
    return redirect(url_for("basic"), code=303)


@app.post("/basic/shopping/<int:product_id>")
def basic_shopping_step(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409)
    try:
        barcode_stock.change_shopping_quantity(product_id, request.form.get("direction"))
    except Exception:
        return "No se pudo actualizar la lista. Comprueba Grocy antes de reintentar.", 409
    finally:
        LOCK.release()
    return redirect(url_for("basic"), code=303)


def receipt_path(receipt_id):
    if not re.fullmatch(r"[a-f0-9]{32}", receipt_id):
        raise ValueError("Identificador de ticket no válido")
    return DATA / (receipt_id + ".json")


def run_import(receipt_id, mode):
    return subprocess.run([sys.executable, str(ROOT / "importer.py"), str(receipt_path(receipt_id)), mode],
                          cwd=ROOT, text=True, capture_output=True, timeout=180, check=False)


from api_variants import register_variant_routes
from api_inventory import register_inventory_routes
from api_shopping import register_shopping_routes
from api_receipts import register_receipt_routes
from api_catalog import register_catalog_routes
from api_aliases import register_alias_routes
from api_photos import register_photo_routes
register_variant_routes(app, barcode_stock, variant_catalog, LOCK)
register_inventory_routes(app, barcode_stock, LOCK)
register_shopping_routes(app, barcode_stock, shopping_match_queue, LOCK, lambda: INGRESS_MODE, csrf_token)
register_receipt_routes(app, DATA, ALLOWED, extract, lambda rid, mode: run_import(rid, mode), LOCK)
register_catalog_routes(app, barcode_stock, LOCK)
register_photo_routes(app, barcode_stock, LOCK)
register_alias_routes(app)


if __name__ == "__main__":
    if not configured():
        raise SystemExit("Configure WEB_PASSWORD and WEB_SESSION_SECRET")
    app.run(host="127.0.0.1", port=int(os.getenv("WEB_PORT", "8765")), debug=False)
