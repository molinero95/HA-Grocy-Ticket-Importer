#!/usr/bin/env python3
"""Local-only prototype UI. NOT a Home Assistant ingress add-on."""
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template_string, request, session, url_for
from werkzeug.utils import secure_filename

import extract
import barcode_stock
import product_images

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DATA = Path(os.environ.get("RECEIPT_DATA_DIR", str(ROOT / "runtime" / "receipts")))
ALLOWED = {".pdf", ".jpg", ".jpeg", ".png"}
LOCK = threading.Lock()
INGRESS_MODE = os.environ.get("HA_INGRESS_MODE") == "1"

class IngressPrefixMiddleware:
    """Use the ingress prefix for URL generation; proxy strips it from PATH_INFO."""
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __call__(self, environ, start_response):
        prefix = environ.get("HTTP_X_INGRESS_PATH", "").rstrip("/")
        if INGRESS_MODE and prefix.startswith("/api/hassio_ingress/"):
            environ["SCRIPT_NAME"] = prefix
        return self.wrapped(environ, start_response)


app = Flask(__name__)
app.wsgi_app = IngressPrefixMiddleware(app.wsgi_app)
app.config.update(
    SECRET_KEY=os.environ.get("WEB_SESSION_SECRET", ""),
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
)

PAGE = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tickets → Grocy</title>
<style>body{font:16px system-ui;max-width:760px;margin:auto;padding:24px;color:#202936}
header{display:flex;justify-content:space-between;align-items:center}
section{background:#f4f6f8;padding:18px;border-radius:12px;margin:16px 0}
input,button{font:inherit;padding:10px;margin:5px 0;max-width:100%}
button{cursor:pointer}table{border-collapse:collapse;width:100%}
td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}
.review{color:#a34b00}.error{color:#a40000}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>
<header><h1>Tickets → Grocy</h1>{% if authenticated and not ingress_mode %}
<form action="{{ url_for('logout') }}" method="post">
<input type="hidden" name="csrf" value="{{ csrf }}"><button>Salir</button></form>{% endif %}</header>
{% if message %}<section><strong>{{ message }}</strong></section>{% endif %}
{% if not authenticated %}<section><form method="post" action="{{ url_for('login') }}">
<input type="password" name="password" placeholder="Contraseña" required>
<input type="hidden" name="csrf" value="{{ csrf }}">
<button type="submit">Entrar</button></form></section>
{% else %}
<section><h2>Añadir producto por código de barras</h2>
<form method="post" action="{{ url_for('barcode_add') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label>Código de barras (EAN/UPC) <input name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" required></label>
<label>Nombre (solo si es nuevo) <input name="name" maxlength="200" placeholder="Leche entera 1 L"></label>
<button type="submit">Añadir 1 al stock</button></form>
<p>Si el código no está registrado, indica un nombre para crear el producto. Si existe, se reutiliza.</p></section>
<section><h2>Asociar código a producto existente</h2>
<form method="post" action="{{ url_for('barcode_associate') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label>Código de barras <input name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" required></label>
<label>Producto existente <select name="product_id" required>
<option value="">Selecciona un producto</option>
{% for p in products %}<option value="{{ p.id }}">{{ p.name }}</option>{% endfor %}
</select></label>
<button type="submit">Asociar código sin cambiar stock</button></form>
<p>Permite reconocer al instante productos ya registrados y evita duplicados.</p>
</section>
<section><h2>Buscar foto por código de barras</h2>
<form method="post" action="{{ url_for('barcode_photo') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label>Código de barras <input name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" required></label>
<button type="submit">Buscar imagen</button></form>
{% if photo %}<p><strong>{{ photo.name }}</strong></p>
<img src="{{ photo.image_url }}" alt="Fotografía de {{ photo.name }}" width="180" loading="lazy">
<p><a href="{{ photo.source_url }}" target="_blank" rel="noopener noreferrer">{{ photo.attribution }}</a></p>
<p>Esta foto se muestra como vista previa. Todavía no se guarda en la ficha de Grocy.</p>
{% endif %}</section>
<section><h2>Eliminar una unidad del stock</h2>
<form method="post" action="{{ url_for('barcode_remove_preview') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label>Código de barras <input name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" required></label>
<button type="submit">Buscar unidad para descontar</button></form>
<p>Esta opción consume una unidad; nunca elimina el producto de la base de datos.</p></section>
{% if remove_candidate %}
<section><h3>Confirmar salida de stock</h3>
<p>Producto: <strong>{{ remove_candidate.name }}</strong> ({{ remove_candidate.barcode }})</p>
<form method="post" action="{{ url_for('barcode_remove') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input type="hidden" name="barcode" value="{{ remove_candidate.barcode }}">
<button type="submit">Confirmar: quitar 1 unidad</button></form></section>
{% endif %}
<section><h2>Subir ticket</h2><p>PDF, JPG o PNG (máximo 12 MiB). La subida no modifica Grocy.</p>
<form method="post" action="{{ url_for('upload') }}" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input type="file" name="ticket" accept=".pdf,.jpg,.jpeg,.png" required>
<button type="submit">Extraer y revisar</button></form></section>
{% if receipt %}
<section><h2>{{ receipt.merchant }} · {{ receipt.receipt_date }} · {{ receipt.total }} €</h2>
<p>{{ receipt.items|length }} líneas. Las marcadas como revisión se omitirán al importar.</p>
<table><thead><tr><th>Producto</th><th>Cantidad</th><th>Precio/u</th><th>Estado</th></tr></thead><tbody>
{% for item in receipt.items %}<tr><td>{{ item.name }}</td><td>{{ item.quantity }}</td>
<td>{{ item.unit_price }} €</td><td class="{{ 'review' if item.ambiguous else '' }}">
{{ 'Revisar: ' + item.reason if item.ambiguous else 'Propuesto' }}</td></tr>{% endfor %}
</tbody></table>
<form method="post" action="{{ url_for('preview', rid=rid) }}">
<input type="hidden" name="csrf" value="{{ csrf }}"><button>Simular en Grocy</button></form>
{% if simulation %}<h3>Simulación</h3><pre>{{ simulation }}</pre>
{% if can_commit %}<form method="post" action="{{ url_for('commit', rid=rid) }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<button type="submit">Confirmar importación</button></form>{% endif %}
{% endif %}
</section>{% endif %}
{% endif %}</html>"""

def configured():
    return bool(app.secret_key and (INGRESS_MODE or os.environ.get("WEB_PASSWORD")))

@app.before_request
def protect():
    if not configured():
        abort(503, "Configure WEB_PASSWORD and WEB_SESSION_SECRET in .env")
    if request.method == "POST":
        token = session.get("csrf")
        if not token or not hmac.compare_digest(request.form.get("csrf", ""), token):
            abort(403)
    if request.endpoint not in ("index", "login", "static") and not (INGRESS_MODE or session.get("auth")):
        abort(401)

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]

def render(message="", receipt=None, rid=None, simulation=None, can_commit=False, remove_candidate=None, photo=None):
    return render_template_string(PAGE, csrf=csrf_token(), message=message,
                                  receipt=receipt, rid=rid, simulation=simulation,
                                  can_commit=can_commit, remove_candidate=remove_candidate, photo=photo,
                                  products=product_choices(), authenticated=INGRESS_MODE or bool(session.get("auth")),
                                  ingress_mode=INGRESS_MODE)

def receipt_path(rid):
    if len(rid) != 32 or any(c not in "0123456789abcdef" for c in rid):
        abort(404)
    return DATA / (rid + ".json")

def load_receipt(rid):
    path = receipt_path(rid)
    if not path.is_file():
        abort(404)
    return json.loads(path.read_text(encoding="utf-8"))

@app.get("/")
def index():
    return render()

@app.post("/login")
def login():
    if hmac.compare_digest(request.form.get("password", ""), os.environ["WEB_PASSWORD"]):
        session.clear()
        session["auth"] = True
        return redirect(url_for("index"))
    return render("Contraseña incorrecta"), 401

@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

def product_choices():
    if not (INGRESS_MODE or session.get("auth")):
        return []
    try:
        return barcode_stock.list_products()
    except Exception:
        return []

@app.post("/barcode/associate")
def barcode_associate():
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        result = barcode_stock.associate_barcode(request.form.get("barcode", ""),
                                                 request.form.get("product_id", ""))
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("Error de Grocy. Comprueba la asociación antes de reintentar."), 502
    finally:
        LOCK.release()
    return render(("El código ya estaba asociado a " if result["already_linked"]
                   else "Código asociado a ") + result["name"] + ". Stock sin cambios.")

@app.post("/barcode/photo")
def barcode_photo():
    try:
        photo = product_images.lookup_image(request.form.get("barcode", ""))
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("No se ha podido consultar Open Food Facts."), 502
    if not photo:
        return render("No se ha encontrado una imagen para ese código.")
    return render("Foto encontrada por código exacto", photo=photo)

@app.post("/barcode/add")
def barcode_add():
    barcode = request.form.get("barcode", "")
    name = request.form.get("name", "")
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        result = barcode_stock.add_one(barcode, name,
                                      location_id=int(os.getenv("GROCY_LOCATION_ID", "2")))
    except (barcode_stock.BarcodeError, ValueError) as exc:
        return render("No se pudo añadir: " + str(exc)), 400
    except Exception:
        return render("Error de Grocy. Comprueba el stock antes de volver a intentarlo."), 502
    finally:
        LOCK.release()
    return render("Añadida 1 unidad al stock" + (" (producto nuevo)" if result["created"] else ""))

@app.post("/barcode/remove-preview")
def barcode_remove_preview():
    try:
        barcode = barcode_stock.validate_barcode(request.form.get("barcode", ""))
        product = barcode_stock.find_product(barcode)
        if product is None:
            return render("No hay ningún producto con ese código"), 404
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("No se pudo consultar Grocy"), 502
    session["remove_barcode"] = barcode
    return render(remove_candidate={"barcode": barcode, "name": product["name"]})

@app.post("/barcode/remove")
def barcode_remove():
    barcode = request.form.get("barcode", "")
    if session.pop("remove_barcode", None) != barcode:
        abort(403, "Primero confirma el producto")
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        result = barcode_stock.remove_one(barcode)
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("Error de Grocy. Comprueba el stock antes de reintentar."), 502
    finally:
        LOCK.release()
    return render("Descontada 1 unidad de " + result["name"] + ". El producto sigue en el catálogo.")

@app.post("/upload")
def upload():
    upload = request.files.get("ticket")
    if not upload or Path(secure_filename(upload.filename or "")).suffix.lower() not in ALLOWED:
        abort(400, "Formato no admitido")
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    rid = secrets.token_hex(16)
    source = DATA / (rid + Path(upload.filename).suffix.lower())
    upload.save(source)
    try:
        receipt = extract.extract(source)
        receipt_path(rid).write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    finally:
        source.unlink(missing_ok=True)
    session["receipt_id"] = rid
    session.pop("previewed", None)
    return render("Revisa el ticket antes de importarlo", receipt, rid)

def check_receipt_session(rid):
    if session.get("receipt_id") != rid:
        abort(403)
    return load_receipt(rid)

def run_import(rid, mode):
    return subprocess.run([sys.executable, str(ROOT / "importer.py"), str(receipt_path(rid)), mode],
                          cwd=ROOT, text=True, capture_output=True, timeout=180, check=False)

@app.post("/preview/<rid>")
def preview(rid):
    receipt = check_receipt_session(rid)
    result = run_import(rid, "--dry-run")
    if result.returncode != 0:
        session.pop("previewed", None)
        return render("No se puede importar: " + result.stderr[-1200:], receipt, rid), 400
    session["previewed"] = rid
    return render("Simulación completada", receipt, rid, result.stdout, True)

@app.post("/commit/<rid>")
def commit(rid):
    receipt = check_receipt_session(rid)
    if session.get("previewed") != rid:
        abort(403, "Primero realiza la simulación")
    session.pop("previewed", None)
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra importación está en marcha")
    try:
        result = run_import(rid, "--commit")
    except subprocess.TimeoutExpired:
        return render("Tiempo agotado. Comprueba Grocy antes de reintentar.", receipt, rid), 500
    finally:
        LOCK.release()
    if result.returncode:
        return render("Importación interrumpida: no reintentes sin conciliar. " + result.stderr[-1000:],
                      receipt, rid, result.stdout), 500
    return render("Importación terminada. No vuelvas a confirmar este ticket.",
                  receipt, rid, result.stdout)

if __name__ == "__main__":
    if not configured():
        raise SystemExit("Set WEB_PASSWORD and WEB_SESSION_SECRET in local .env")
    # Localhost only. Mobile access requires a separately secured HA ingress integration.
    app.run(host="127.0.0.1", port=int(os.getenv("WEB_PORT", "8765")), debug=False)
