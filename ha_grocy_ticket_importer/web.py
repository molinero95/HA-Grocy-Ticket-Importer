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
from flask import Flask, abort, jsonify, redirect, render_template_string, request, session, url_for
from werkzeug.utils import secure_filename

import extract
import barcode_stock
import product_images

ROOT = Path(__file__).resolve().parent
load_dotenv(os.environ.get("GROCY_ENV_FILE", str(ROOT / ".env")))
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
<title>Despensa · Grocy</title>
<style>
:root{color-scheme:light;--bg:#f5f7f5;--card:#fff;--text:#182925;--muted:#62736d;--primary:#126948;--primary-dark:#0b5136;--line:#dce6df;--soft:#e9f5ee;--danger:#aa4038}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:16px}
body{font:16px/1.48 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:920px;margin:0 auto;padding:0 20px 88px;background:var(--bg);color:var(--text)}
header{padding:22px 0 12px;display:flex;justify-content:space-between;align-items:center;gap:14px}
header h1{font-size:clamp(1.55rem,5vw,2.15rem);line-height:1.15;margin:0;font-weight:800;letter-spacing:-.035em}
header p{margin:6px 0 0;color:var(--muted);font-size:.93rem}
h2{font-size:1.17rem;line-height:1.3;margin:0 0 14px}
h3{font-size:1.05rem}
p{margin:10px 0;color:var(--muted)}
section{background:var(--card);padding:22px;border-radius:18px;margin:18px 0;border:1px solid var(--line);box-shadow:0 3px 16px rgba(24,41,37,.035);scroll-margin-top:20px}
section:target{border-color:#9bcab2}
label{display:block;font-weight:650;margin:14px 0 7px}
input,button,select{font:inherit}
input:not([type=hidden]),button,select{min-height:46px}
input:not([type=hidden]),select{width:100%;max-width:100%;border:1px solid #bacdc2;background:white;color:var(--text);border-radius:11px;padding:11px 12px;outline-offset:2px}
input:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid #50a97c;outline-offset:3px}
button{cursor:pointer;border:0;border-radius:11px;padding:12px 16px;background:var(--primary);color:white;font-weight:700;touch-action:manipulation}
button:hover{background:var(--primary-dark)}
button:disabled{opacity:.45;cursor:not-allowed}
button[type=submit]{margin-top:16px;width:100%}
a{color:var(--primary)}
table{border-collapse:collapse;width:100%}
td,th{padding:10px 8px;border-bottom:1px solid var(--line);text-align:left}
.review{color:#a34b00}.error{color:var(--danger)}
pre{white-space:pre-wrap;overflow-wrap:anywhere}
.product-results{max-height:275px;overflow-y:auto;overscroll-behavior:contain;margin:8px 0;border:1px solid var(--line);border-radius:12px;background:white}
.product-result{display:block;width:100%;text-align:left;background:white;color:var(--text);border:0;border-bottom:1px solid var(--line);border-radius:0;cursor:pointer;padding:13px 14px;margin:0;font-weight:500}
.product-result:hover,.product-result:focus,.product-result[aria-selected=true]{background:var(--soft);color:var(--primary-dark)}
.product-result[hidden]{display:none}
#selected-product-label{font-weight:700;color:var(--primary)}
.barcode-input-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:7px}
.barcode-input-row input{min-width:130px;flex:1}
.scan-trigger{background:var(--soft);border:1px solid #b9d8c6;border-radius:11px;color:var(--primary-dark);flex-shrink:0}
.scan-trigger:hover{background:#d3e9dc;color:var(--primary-dark)}
#scanner-dialog{border:0;border-radius:18px;padding:20px;max-width:min(94vw,540px);width:100%;background:var(--card);color:var(--text)}
#scanner-dialog::backdrop{background:rgba(0,0,0,.75)}
#scanner-video{width:100%;aspect-ratio:4/3;object-fit:cover;background:#000;border-radius:12px}
#scanner-status{min-height:2.4em}
#scanner-stop{width:100%;background:#e7ece9;color:var(--text)}
.hero{background:linear-gradient(130deg,#e1f1e7,#f6faf6);border:1px solid #c7e2d2;padding:20px;border-radius:18px;margin:10px 0 18px}
.hero strong{font-size:1.05rem}
.hero p{margin:6px 0 0}
.action-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:16px}
.action-link{display:flex;min-height:100px;flex-direction:column;align-items:flex-start;justify-content:center;gap:3px;text-decoration:none;border:1px solid #b9dcc8;border-radius:14px;background:#fff;padding:14px;color:var(--text)}
.action-link strong{font-size:1rem}
.action-link span{font-size:1.35rem}
.action-link small{font-size:.78rem;color:var(--muted)}
.action-link:focus,.action-link:hover{background:#e9f5ee;border-color:var(--primary)}
.notice{border-left:4px solid #8fbe9e;padding-left:14px}
.status-message{background:#e2f2e9;border-color:#b8d8c5}
.section-eyebrow{font-size:.76rem;letter-spacing:.06em;text-transform:uppercase;font-weight:800;color:var(--primary);margin:0 0 8px}
.helper{font-size:.9rem}
.ticket-table{overflow-x:auto;-webkit-overflow-scrolling:touch}
.main-tabs{display:flex;gap:8px;margin:10px 0 18px}
.main-tabs a{flex:1;display:flex;justify-content:center;align-items:center;text-decoration:none;border:1px solid var(--line);border-radius:13px;background:white;font-weight:700;min-height:52px}
.main-tabs a[aria-current=page]{background:var(--primary);color:white}
.action-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.back-link{display:inline-flex;align-items:center;min-height:40px;text-decoration:none;font-weight:700}
.inventory-list{margin-top:14px}
.inventory-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 0;border-bottom:1px solid var(--line)}
.pantry-row{display:grid;grid-template-columns:minmax(0,1fr) 144px;gap:12px;align-items:center}
.pantry-info{min-width:0;overflow-wrap:anywhere}
.pantry-side{min-width:0;display:flex;flex-direction:column;align-items:stretch;gap:7px}
.pantry-side .inventory-quantity{text-align:center}
.shopping-stepper{display:grid;grid-template-columns:37px minmax(0,1fr) 37px;gap:3px;align-items:center;width:100%;background:var(--soft);border-radius:12px;padding:4px;border:1px solid #b9d8c6}
.shopping-stepper form{margin:0}
.shopping-stepper button{width:37px;min-height:37px;margin:0;padding:0;border-radius:9px;font-size:1.2rem}
.shopping-stepper .minus{background:#dce9e1;color:var(--primary-dark)}
.shopping-stepper button:disabled{opacity:.35}
.shopping-stepper output{text-align:center;white-space:nowrap;font-size:.85rem;font-weight:750;color:var(--primary-dark)}
.shopping-stepper output small{display:block;font-size:.66rem;font-weight:500}
.inventory-row[hidden]{display:none}
.product-detail-link{display:block;text-decoration:none;color:var(--text);padding:4px 0}
.product-detail-link:hover strong{text-decoration:underline}
.product-sheet img{max-width:100%;height:auto;border-radius:12px}
.product-thumb{width:52px;height:52px;border-radius:11px;object-fit:contain;background:#f0f4f1;border:1px solid var(--line);flex-shrink:0}
.product-photo-full{width:210px;max-width:100%;height:210px;object-fit:contain;background:#f4f6f5;border-radius:14px;border:1px solid var(--line)}
.product-name-with-photo{display:flex;gap:11px;align-items:center;min-width:0}
.product-name-with-photo>div{min-width:0}
.photo-preview{margin:10px 0}
.photo-preview img{width:140px;height:140px;object-fit:contain;border-radius:12px;border:1px solid var(--line)}

.inventory-row strong{display:block}
.inventory-row small{display:block;color:var(--muted);font-size:.79rem;margin-top:3px}
.inventory-quantity{text-align:right;min-width:80px}
.inventory-quantity form{margin-top:7px}
.inventory-quantity button{min-height:36px;padding:6px 10px;font-size:.8rem}
.shopping-add-link{display:inline-flex;align-items:center;justify-content:center;min-height:36px;padding:6px 10px;font-size:.8rem;text-decoration:none;margin-top:8px}
.consume-replenish{display:flex;align-items:center;gap:10px}
.consume-replenish input{width:22px;height:22px;flex-shrink:0}
.shopping-controls{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end}
.shopping-controls button{min-height:38px;padding:7px 10px;font-size:.82rem}
.quantity-unknown{color:#a34b00;font-size:.85rem}
.version-label{border:1px solid var(--line);border-radius:999px;background:var(--soft);padding:6px 11px;text-decoration:none;font-size:.77rem;font-weight:750;white-space:nowrap}
.about-list{display:grid;grid-template-columns:minmax(100px,1fr) 2fr;gap:12px 8px;overflow-wrap:anywhere}
.about-list dt{color:var(--muted);font-weight:650}
.about-list dd{margin:0}
.bottom-nav{display:none}
@media(max-width:600px){
 body{padding:0 12px 96px;font-size:16px}
 header{padding:18px 3px 12px}
 section{padding:17px 15px;border-radius:15px;margin:13px 0}
 .hero{padding:16px;margin-top:4px}
 .action-grid{gap:7px}
 .action-link{min-height:86px;padding:11px 8px}
 .action-link strong{font-size:.88rem}
 .action-link small{font-size:.72rem}
 .barcode-input-row{flex-wrap:nowrap}
 .barcode-input-row input{min-width:0}
 .scan-trigger{padding:10px 12px;min-width:104px}
 .bottom-nav{position:fixed;display:flex;bottom:0;left:0;right:0;padding:7px max(10px,env(safe-area-inset-right)) calc(8px + env(safe-area-inset-bottom)) max(10px,env(safe-area-inset-left));gap:7px;background:rgba(255,255,255,.97);border-top:1px solid var(--line);box-shadow:0 -5px 18px rgba(0,0,0,.06);z-index:10}
 .bottom-nav a{min-height:49px;flex:1;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:.81rem;font-weight:750;color:var(--primary);border-radius:10px;background:var(--soft);text-align:center;padding:4px}
 .bottom-nav a:focus,.bottom-nav a:hover{background:#cfe6d8}
 .bottom-nav a[aria-current=page]{background:var(--primary);color:#fff}
 .main-tabs{display:none}
 .action-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
 .action-link{min-height:108px}
 .inventory-row{gap:8px}
 .pantry-row{grid-template-columns:minmax(0,1fr) 132px;gap:8px}
 .shopping-stepper{grid-template-columns:33px minmax(0,1fr) 33px;gap:2px}
 .shopping-stepper button{width:33px;min-height:36px}
 #scanner-dialog{padding:14px}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style>
<header><div><h1>🌿 Despensa</h1><p>Tu inventario, sin complicaciones</p></div><a class="version-label" href="{{ url_for('index', view='about') }}" aria-label="Acerca de Despensa, versión {{ app_version }}">v{{ app_version }}</a>{% if authenticated and not ingress_mode %}
<form action="{{ url_for('logout') }}" method="post">
<input type="hidden" name="csrf" value="{{ csrf }}"><button>Salir</button></form>{% endif %}</header>
{% if message %}<section class="status-message" role="status"><strong>{{ message }}</strong></section>{% endif %}
{% if not authenticated %}<section><form method="post" action="{{ url_for('login') }}">
<input type="password" name="password" placeholder="Contraseña" required>
<input type="hidden" name="csrf" value="{{ csrf }}">
<button type="submit">Entrar</button></form></section>
{% else %}
<nav class="main-tabs" aria-label="Secciones principales"><a href="{{ url_for('index', view='shopping') }}" {% if view == 'shopping' %}aria-current="page"{% endif %}>🛒 Lista de la compra</a><a href="{{ url_for('index', view='inventory') }}" {% if view == 'inventory' or view == 'product' %}aria-current="page"{% endif %}>📦 Mi despensa</a><a href="{{ url_for('index', view='actions') }}" {% if view not in ('shopping','inventory','product','shopping_add') %}aria-current="page"{% endif %}>⚡ Acciones</a></nav>
{% if view == 'shopping' %}
<section><p class="section-eyebrow">Sincronizada con Grocy</p><h2>🛒 Lista de la compra</h2>
{% if shopping_error %}<p role="alert">No se pudo cargar la lista desde Grocy.</p>{% else %}
<p>{{ shopping|length }} artículos en la lista. Marcarlos como comprados no añade stock automáticamente.</p>
{% if not shopping %}<p>Tu lista está vacía. Añade un artículo desde Mi despensa.</p>{% endif %}
<div class="inventory-list">
{% for item in shopping %}
<article class="inventory-row">
<div class="product-name-with-photo">{% if item.image_url %}<img class="product-thumb" src="{{ item.image_url }}" alt="" loading="lazy" referrerpolicy="no-referrer">{% endif %}<div><strong {% if item.done %}style="text-decoration:line-through;opacity:.6"{% endif %}>{{ item.name }}</strong><small>{{ item.amount }} {{ item.unit }}</small></div></div>
<div class="shopping-controls">
<form method="post" action="{{ url_for('shopping_toggle', item_id=item.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="done" value="{{ '0' if item.done else '1' }}">
<button type="submit" class="scan-trigger">{{ '↩ Pendiente' if item.done else '✓ Comprado' }}</button></form>
<form method="post" action="{{ url_for('shopping_remove', item_id=item.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit" class="scan-trigger">✕ Quitar</button></form>
</div>
</article>
{% endfor %}</div>{% endif %}
</section>
{% elif view == 'shopping_add' %}
<section>
<p class="section-eyebrow">Lista de la compra</p>
{% if shopping_product %}
<h2>Añadir {{ shopping_product.name }}</h2>
<form method="post" action="{{ url_for('shopping_add', product_id=shopping_product.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label for="shopping-amount">Cantidad</label>
<input id="shopping-amount" name="amount" type="number" min="0.01" step="0.01" value="1" inputmode="decimal" required>
<label for="shopping-unit">Unidad de medida</label>
<select id="shopping-unit" name="unit_id" required>
{% for u in shopping_product.units %}<option value="{{ u.id }}">{{ u.name }}</option>{% endfor %}
</select>
<p class="helper">Máximo dos decimales. Las unidades se limitan a las configuradas en Grocy para este producto; no cambia tus existencias.</p>
<button type="submit">Añadir a la lista</button>
</form>
{% else %}<p role="alert">No se pudo encontrar este producto.</p>{% endif %}
</section>
{% elif view == 'inventory' %}
<section class="inventory-panel"><p class="section-eyebrow">Inventario actual</p><h2>Mi despensa</h2>
{% if inventory_error %}<p role="alert">No se ha podido consultar el inventario de Grocy. Inténtalo más tarde.</p>{% else %}
<p>{{ inventory|length }} productos registrados. Cantidades leídas de Grocy.</p>
<label for="inventory-search">Buscar en mi despensa</label><input id="inventory-search" type="search" autocomplete="off" placeholder="Busca leche, arroz, tomate…">
<div class="inventory-list" id="inventory-list">
{% for p in inventory %}
<article class="inventory-row pantry-row" data-name="{{ p.name }}">
<div class="pantry-info product-name-with-photo">{% if p.image_url %}<img class="product-thumb" src="{{ p.image_url }}" alt="" loading="lazy" referrerpolicy="no-referrer">{% endif %}<a class="product-detail-link" href="{{ url_for('index', view='product', product_id=p.id) }}"><strong>{{ p.name }}</strong><small>Ver y editar ficha →</small></a></div>
<div class="pantry-side">
<div class="inventory-quantity">{% if p.amount is none %}<span class="quantity-unknown">Sin datos</span>{% else %}<strong>{{ p.amount }}</strong><small>{{ p.unit }}</small>{% endif %}</div>
<div class="shopping-stepper" aria-label="Cantidad de {{ p.name }} en lista de compra">
<form method="post" action="{{ url_for('shopping_step', product_id=p.id, direction='minus') }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="minus" type="submit" aria-label="Quitar {{ p.shopping_step }} {{ p.shopping_unit }} de {{ p.name }}" {% if not p.shopping_can_subtract %}disabled{% endif %}>−</button></form>
<output>{{ p.shopping_amount }}<small>{{ p.shopping_unit }}</small></output>
<form method="post" action="{{ url_for('shopping_step', product_id=p.id, direction='plus') }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit" aria-label="Añadir {{ p.shopping_step }} {{ p.shopping_unit }} de {{ p.name }}">+</button></form>
</div></div>
</article>
{% endfor %}
</div><p id="inventory-empty" hidden>No hay productos que coincidan con la búsqueda.</p>
{% endif %}
</section>
{% elif view == 'actions' %}
<div class="hero"><strong>¿Qué quieres hacer?</strong><p>Elige una operación. Cada una tiene su propia pantalla.</p>
<nav class="action-grid" aria-label="Acciones de Despensa">
<a class="action-link" href="{{ url_for('index', view='add') }}"><span aria-hidden="true">➕</span><strong>Añadir producto</strong><small>Crear artículo nuevo</small></a>
<a class="action-link" href="{{ url_for('index', view='remove') }}"><span aria-hidden="true">➖</span><strong>Consumir producto</strong><small>Quitar del stock</small></a>
<a class="action-link" href="{{ url_for('index', view='ticket') }}"><span aria-hidden="true">🧾</span><strong>Subir ticket</strong><small>Importar compra</small></a>
</nav></div>
{% else %}
<p><a class="back-link" href="{{ url_for('index', view='inventory') if view == 'product' else url_for('index', view='actions') }}">← {{ 'Volver a mi despensa' if view == 'product' else 'Volver a acciones' }}</a></p>
{% endif %}
{% if view == 'about' %}
<section><p class="section-eyebrow">Información</p><h2>Acerca de Despensa</h2>
<dl class="about-list">
<dt>Versión</dt><dd>v{{ app_version }}</dd>
<dt>Instalación</dt><dd>{{ app_distribution }}</dd>
<dt>Conexión con Grocy</dt><dd>{{ 'Configurada' if grocy_configured else 'Sin configurar' }} (no comprobada en tiempo real)</dd>
<dt>Código fuente</dt><dd><a href="https://github.com/molinero95/HA-Grocy-Ticket-Importer" rel="noopener noreferrer" target="_blank">GitHub · HA-Grocy-Ticket-Importer</a></dd>
</dl>
<p class="helper">La versión identifica el complemento abierto. Para ver el estado real de Grocy, consulta Mi despensa.</p>
</section>
{% endif %}
{% if view == 'product' %}
<section class="product-sheet">
{% if product %}
<p class="section-eyebrow">Ficha del artículo</p>
<h2>{{ product.name }}</h2>
<div class="photo-preview"><img id="product-photo-display" {% if product.image_url %}src="{{ product.image_url }}"{% else %}hidden{% endif %} alt="Imagen del producto {{ product.name }}" loading="lazy" referrerpolicy="no-referrer"></div>
<p>Las unidades por envase son informativas. Cambiarlas <strong>no modifica las existencias</strong> de Grocy.</p>
<form method="post" action="{{ url_for('product_update', product_id=product.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label for="edit-product-name">Nombre del artículo</label>
<input id="edit-product-name" name="name" maxlength="200" value="{{ product.name }}" required>
<label for="edit-unit">Unidad de medida del stock</label>
<select id="edit-unit" name="unit_id" required>
{% for u in product.units %}<option value="{{ u.id }}" {% if u.id == product.unit_id %}selected{% endif %}>{{ u.name }}</option>{% endfor %}
</select>
<p class="helper">Si hay existencias ({{ product.stock_amount }}), cambiar la unidad requiere una conversión previa en Grocy para no tratar unidades como kg.</p>
<label for="edit-pack-size">Unidades por envase</label>
<input id="edit-pack-size" name="pack_size" type="number" min="1" max="1000" step="1" value="{{ product.pack_size }}" required>
<p class="helper">Ejemplo: si el aroma de vainilla contiene 4 botellitas, indica 4. Se seguirá contando como un envase hasta que configuremos otra unidad de stock.</p>
<button type="submit">Guardar cambios</button>
</form>
<h3>Ajustar cantidad disponible</h3>
<p>Stock actual: <strong>{{ product.stock_amount }} {{ product.units|selectattr('id', 'equalto', product.unit_id)|map(attribute='name')|first|default('unidades') }}</strong></p>
<form method="post" action="{{ url_for('product_stock_save', product_id=product.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input type="hidden" name="expected_amount" value="{{ product.stock_amount }}">
<label for="edit-stock-amount">Cantidad total que tengo</label>
<input id="edit-stock-amount" name="desired_amount" inputmode="decimal" type="number" step="0.01" min="0" value="{{ product.stock_amount }}" required>
<p class="helper">Máximo dos decimales. Al guardar se actualizarán directamente las existencias en Grocy.</p>
<button type="submit">Guardar cantidad</button>
</form>
<h3>Asociar código de barras</h3>
<p class="helper">El artículo ya está seleccionado. Asociar un código no cambia las existencias.</p>
<form method="post" action="{{ url_for('product_barcode_add', product_id=product.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label>Código <span class="barcode-input-row"><input name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" autocomplete="off" required><button class="scan-trigger" type="button" aria-label="Escanear código para este artículo">📷 Escanear</button></span></label>
<div class="photo-preview"><img class="barcode-photo-preview" hidden alt="Fotografía encontrada" referrerpolicy="no-referrer"><p class="photo-status helper" aria-live="polite"></p></div>
<button type="submit">Asociar código a este artículo</button></form>
<h3>Fotografía</h3>
{% if product.image_url %}<p class="helper">Imagen guardada desde Open Food Facts.</p>{% endif %}
{% if product.barcodes %}
<form method="post" action="{{ url_for('product_photo', product_id=product.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<button type="submit">📷 Buscar foto por código de barras</button>
</form>
<p class="helper">Códigos: {{ product.barcodes|join(', ') }}</p>
{% else %}
<p>Este producto aún no tiene un código de barras asociado. Puedes vincularlo en esta misma ficha.</p>
{% endif %}
{% else %}<p role="alert">No se ha podido cargar la ficha del producto.</p>{% endif %}
</section>
{% endif %}
{% if view == 'add' %}
<section id="entrada"><p class="section-eyebrow">Catálogo</p><h2>Añadir producto nuevo</h2>
<p>Solo se crea si no existe ya en Grocy. Si coincide el nombre o el código de barras, podrás abrir su ficha para editarlo.</p>
{% if existing_product %}
<div class="status-message" role="status">
<strong>Este producto ya existe: {{ existing_product.name }}</strong>
<p>No se ha creado ningún duplicado ni modificado el stock.</p>
<a class="back-link" href="{{ url_for('index', view='product', product_id=existing_product.id) }}">✏️ Ir a editar producto →</a>
</div>
{% endif %}
<form method="post" action="{{ url_for('barcode_add') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input type="hidden" name="image_url" class="barcode-image-url" value="">
<label for="new-product-name">Nombre del producto</label>
<input id="new-product-name" name="name" maxlength="200" placeholder="Tomate en rama" required>
<label>Código de barras (opcional) <span class="barcode-input-row"><input name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" autocomplete="off" placeholder="Escanear o escribir"><button class="scan-trigger" type="button" aria-label="Abrir cámara para escanear el código de barras">📷 Escanear</button></span></label>
<div class="photo-preview"><img class="barcode-photo-preview" hidden alt="Fotografía del nuevo producto" referrerpolicy="no-referrer"><p class="photo-status helper" aria-live="polite"></p></div>
<label for="new-product-unit">Unidad de medida</label>
<select id="new-product-unit" name="unit_id" required>
{% for u in new_product_units %}<option value="{{ u.id }}" {% if u.name|lower in ('piece','unidad','unidades') %}selected{% endif %}>{{ u.name }}</option>{% endfor %}
</select>
<label for="new-product-stock">Cantidad inicial en despensa</label>
<input id="new-product-stock" name="initial_stock" type="number" min="0" step="0.01" inputmode="decimal" value="0" required>
<p class="helper">Puedes dejarlo en 0 y añadir existencias más adelante. Máximo dos decimales, por ejemplo 1,50 kg.</p>
<button type="submit">Crear producto</button>
</form>
</section>
{% endif %}
{% if view == 'associate' %}
<section id="asociar"><p class="section-eyebrow">Catálogo</p><h2>Asociar código a producto existente</h2>
<form method="post" action="{{ url_for('barcode_associate') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label>Código de barras <span class="barcode-input-row"><input name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" autocomplete="off" required><button class="scan-trigger" type="button" aria-label="Abrir cámara para escanear el código de barras">📷 Escanear</button></span></label>
<label for="product-search">Buscar producto existente</label>
<input id="product-search" type="search" placeholder="Escribe el nombre (ej. Nutella)" autocomplete="off" aria-controls="product-results" aria-label="Buscar producto">
<input type="hidden" id="selected-product-id" name="product_id" required>
<p id="selected-product-label" role="status" aria-live="polite">No has seleccionado ningún producto.</p>
<div id="product-results" class="product-results" role="listbox" aria-label="Productos encontrados">
{% for p in products %}
<button class="product-result" type="button" role="option" aria-selected="false" data-product-id="{{ p.id }}" data-product-name="{{ p.name }}" {% if loop.index > 8 %}hidden{% endif %}>{{ p.name }}</button>
{% endfor %}
</div>
<p id="product-empty" hidden>No encontramos productos con ese nombre.</p>
<button type="submit" id="associate-submit" disabled>Asociar código sin cambiar stock</button></form>
<p>Permite reconocer al instante productos ya registrados y evita duplicados.</p>
</section>
{% endif %}
{% if view == 'photo' %}
<section id="foto"><p class="section-eyebrow">Fotografías</p><h2>Buscar foto por código de barras</h2>
<form method="post" action="{{ url_for('barcode_photo') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label>Código de barras <span class="barcode-input-row"><input name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" autocomplete="off" required><button class="scan-trigger" type="button" aria-label="Abrir cámara para escanear el código de barras">📷 Escanear</button></span></label>
<button type="submit">Buscar imagen</button></form>
{% if photo %}<p><strong>{{ photo.name }}</strong></p>
<img src="{{ photo.image_url }}" alt="Fotografía de {{ photo.name }}" width="180" loading="lazy">
<p><a href="{{ photo.source_url }}" target="_blank" rel="noopener noreferrer">{{ photo.attribution }}</a></p>
<p>Esta foto se muestra como vista previa. Todavía no se guarda en la ficha de Grocy.</p>
{% endif %}</section>
{% endif %}
{% if view == 'remove' %}
<section id="salida"><p class="section-eyebrow">Salida de productos</p><h2>Consumir producto</h2>
<form method="post" action="{{ url_for('barcode_remove_preview') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label>Código de barras <span class="barcode-input-row"><input name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" autocomplete="off" required><button class="scan-trigger" type="button" aria-label="Abrir cámara para escanear el código de barras">📷 Escanear</button></span></label>
<button type="submit">Buscar producto</button></form>
<p>Selecciona cuánto quieres consumir. El producto no se elimina del catálogo.</p></section>
{% if remove_candidate %}
<section id="confirmar-salida" class="status-message"><h3>Confirmar salida de stock</h3>
<p>Producto: <strong>{{ remove_candidate.name }}</strong> ({{ remove_candidate.barcode }})</p>
<p>Stock disponible: {{ remove_candidate.available }} {{ remove_candidate.unit }}</p>
<form method="post" action="{{ url_for('barcode_remove') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input type="hidden" name="barcode" value="{{ remove_candidate.barcode }}">
<label for="consume-amount">Cantidad a consumir ({{ remove_candidate.unit }})</label>
<input id="consume-amount" name="amount" type="number" min="0.01" step="0.01" max="{{ remove_candidate.available }}" value="1" inputmode="decimal" required>
<label class="consume-replenish"><input type="checkbox" name="add_to_list" value="1"> Añadir esta cantidad a la lista de la compra</label>
<button type="submit">Consumir cantidad</button></form></section>
{% endif %}
{% endif %}
{% if view == 'ticket' %}
<section id="ticket"><p class="section-eyebrow">Compras</p><h2>Subir ticket</h2><p>PDF, JPG o PNG (máximo 12 MiB). La subida no modifica Grocy.</p>
<form method="post" action="{{ url_for('upload') }}" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input type="file" name="ticket" accept=".pdf,.jpg,.jpeg,.png" required>
<button type="submit">Extraer y revisar</button></form></section>
{% if receipt %}
<section><h2>{{ receipt.merchant }} · {{ receipt.receipt_date }} · {{ receipt.total }} €</h2>
<p>{{ receipt['items']|length }} líneas. Las marcadas como revisión se omitirán al importar.</p>
<div class="ticket-table"><table><thead><tr><th>Producto</th><th>Cantidad</th><th>Precio/u</th><th>Estado</th></tr></thead><tbody>
{% for item in receipt['items'] %}<tr><td>{{ item.name }}</td><td>{{ item.quantity }}</td>
<td>{{ item.unit_price }} €</td><td class="{{ 'review' if item.ambiguous else '' }}">
{{ 'Revisar: ' + item.reason if item.ambiguous else 'Propuesto' }}</td></tr>{% endfor %}
</tbody></table></div>
<form method="post" action="{{ url_for('preview', rid=rid) }}">
<input type="hidden" name="csrf" value="{{ csrf }}"><button>Simular en Grocy</button></form>
{% if simulation %}<h3>Simulación</h3><pre>{{ simulation }}</pre>
{% if can_commit %}<form method="post" action="{{ url_for('commit', rid=rid) }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<button type="submit">Confirmar importación</button></form>{% endif %}
{% endif %}
</section>{% endif %}
{% endif %}
<nav class="bottom-nav" aria-label="Navegación móvil">
<a href="{{ url_for('index', view='shopping') }}" {% if view == 'shopping' %}aria-current="page"{% endif %}>🛒 Lista de compra</a>
<a href="{{ url_for('index', view='inventory') }}" {% if view == 'inventory' or view == 'product' %}aria-current="page"{% endif %}>📦 Mi despensa</a>
<a href="{{ url_for('index', view='actions') }}" {% if view not in ('shopping','inventory','product','shopping_add') %}aria-current="page"{% endif %}>⚡ Acciones</a>
</nav>
{% endif %}
<dialog id="scanner-dialog" aria-labelledby="scanner-title">
<h2 id="scanner-title">Escanear código de barras</h2>
<p>Apunta la cámara trasera al código EAN/UPC. No se añadirá ni eliminará stock hasta que confirmes.</p>
<video id="scanner-video" autoplay muted playsinline></video>
<p id="scanner-status" role="status" aria-live="polite">Preparando cámara…</p>
<button type="button" id="scanner-stop">Cerrar cámara</button>
</dialog>
<script>
(() => {
  const dialog = document.getElementById('scanner-dialog');
  if (!dialog) return;
  const video = document.getElementById('scanner-video');
  const status = document.getElementById('scanner-status');
  const stopButton = document.getElementById('scanner-stop');
  let stream = null;
  let scanning = false;
  let target = null;
  let detector = null;
  let frameId = null;
  const supportedCodes = new Set(['ean_13', 'ean_8', 'upc_a', 'upc_e', 'itf']);
  function stop() {
    scanning = false;
    if (frameId !== null) cancelAnimationFrame(frameId);
    frameId = null;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    video.srcObject = null;
    if (dialog.open) dialog.close();
  }
  async function scanFrame() {
    if (!scanning) return;
    if (video.readyState >= 2) {
      try {
        const results = await detector.detect(video);
        if (!scanning) return;
        const found = results.find(result => /^\d{8,14}$/.test(result.rawValue || ''));
        if (found) {
          target.value = found.rawValue;
          target.dispatchEvent(new Event('input', {bubbles: true}));
          stop();
          target.focus();
          return;
        }
      } catch (error) {
        status.textContent = 'No se puede leer la imagen. Prueba a mejorar la iluminación o escribe el código.';
      }
    }
    if (scanning) frameId = requestAnimationFrame(scanFrame);
  }
  async function start(input) {
    stop();
    target = input;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      status.textContent = 'La cámara requiere una conexión segura (HTTPS) y permisos. Introduce el código manualmente.';
      dialog.showModal();
      return;
    }
    if (!('BarcodeDetector' in window)) {
      status.textContent = 'El lector de códigos no está disponible en este navegador. Prueba en Chrome para Android o introduce el código manualmente.';
      dialog.showModal();
      return;
    }
    dialog.showModal();
    try {
      let formats = Array.from(supportedCodes);
      if (typeof BarcodeDetector.getSupportedFormats === 'function') {
        const available = await BarcodeDetector.getSupportedFormats();
        formats = formats.filter(format => available.includes(format));
      }
      if (!formats.length) {
        status.textContent = 'Este dispositivo no admite la lectura de EAN/UPC. Usa la entrada manual.';
        return;
      }
      detector = new BarcodeDetector({formats});
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false, video: {facingMode: {ideal: 'environment'}}
      });
      if (!dialog.open) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
        return;
      }
      video.srcObject = stream;
      await video.play();
      status.textContent = 'Buscando código… Mantén el código visible dentro de la imagen.';
      scanning = true;
      frameId = requestAnimationFrame(scanFrame);
    } catch (error) {
      if (stream) stream.getTracks().forEach(track => track.stop());
      stream = null;
      const denied = error?.name === 'NotAllowedError' || error?.name === 'SecurityError';
      status.textContent = denied
        ? 'Permiso de cámara denegado o bloqueado por Home Assistant. Habilítalo en Android o usa el código manual.'
        : 'No ha sido posible abrir la cámara. Usa el código manual o prueba desde Chrome.';
    }
  }
  // Scanning or typing a complete EAN/UPC previews an image automatically.
  document.querySelectorAll('form input[name="barcode"]').forEach(input => {
    const form = input.closest('form');
    const preview = form?.querySelector('.barcode-photo-preview');
    const status = form?.querySelector('.photo-status');
    const hidden = form?.querySelector('.barcode-image-url');
    if (!preview) return;
    let sequence = 0;
    async function loadPhoto() {
      const id = ++sequence;
      const barcode = input.value.trim();
      if (hidden) hidden.value = '';
      preview.hidden = true;
      preview.removeAttribute('src');
      if (!/^\\d{8,14}$/.test(barcode)) {
        if (status) status.textContent = '';
        return;
      }
      if (status) status.textContent = 'Buscando foto automáticamente…';
      try {
        const url = new URL({{ url_for('photo_lookup')|tojson }}, window.location.href);
        url.searchParams.set('barcode', barcode);
        const response = await fetch(url.toString(), {credentials:'same-origin'});
        if (!response.ok) throw new Error('lookup');
        const data = await response.json();
        if (sequence !== id) return;
        if (data.image_url) {
          preview.src = data.image_url;
          preview.hidden = false;
          if (hidden) hidden.value = data.image_url;
          if (status) status.textContent = 'Foto encontrada en Open Food Facts.';
        } else if (status) status.textContent = 'No hay foto para este código.';
      } catch (_) {
        if (sequence === id && status) status.textContent = 'No se pudo buscar la foto; puedes continuar igualmente.';
      }
    }
    input.addEventListener('input', () => {
      clearTimeout(input._photoTimer);
      input._photoTimer = setTimeout(loadPhoto, 350);
    });
  });
  document.querySelectorAll('.scan-trigger').forEach(button => {
    button.addEventListener('click', () => {
      const input = button.closest('form')?.querySelector('input[name="barcode"]');
      if (input) start(input);
    });
  });
  stopButton.addEventListener('click', stop);
  dialog.addEventListener('cancel', event => {event.preventDefault(); stop();});
  dialog.addEventListener('close', stop);
  document.addEventListener('visibilitychange', () => {if (document.hidden) stop();});
  window.addEventListener('pagehide', stop);
})();
</script>
<script>
(() => {
  const search = document.getElementById('inventory-search');
  if (!search) return;
  const items = Array.from(document.querySelectorAll('.inventory-row'));
  const empty = document.getElementById('inventory-empty');
  const norm = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es');
  function update() {
    const query = norm(search.value.trim());
    let count = 0;
    for (const item of items) {
      const show = norm(item.dataset.name).includes(query);
      item.hidden = !show;
      if (show) count++;
    }
    empty.hidden = count > 0 || !query;
  }
  search.addEventListener('input', update);
})();
</script>
<script>
(() => {
  const search = document.getElementById('product-search');
  if (!search) return;
  const options = Array.from(document.querySelectorAll('.product-result'));
  const selected = document.getElementById('selected-product-id');
  const label = document.getElementById('selected-product-label');
  const submit = document.getElementById('associate-submit');
  const empty = document.getElementById('product-empty');
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim();
  function clearSelection() {
    selected.value = '';
    label.textContent = 'No has seleccionado ningún producto.';
    submit.disabled = true;
    options.forEach(option => option.setAttribute('aria-selected', 'false'));
  }
  function filter() {
    const term = normalize(search.value);
    let count = 0;
    for (const option of options) {
      const match = normalize(option.dataset.productName).includes(term);
      option.hidden = !match || count >= 30;
      if (match) count++;
    }
    empty.hidden = count > 0;
  }
  search.addEventListener('input', () => { clearSelection(); filter(); });
  options.forEach(option => option.addEventListener('click', () => {
    selected.value = option.dataset.productId;
    label.textContent = 'Seleccionado: ' + option.dataset.productName;
    search.value = option.dataset.productName;
    submit.disabled = false;
    options.forEach(other => other.setAttribute('aria-selected', String(other === option)));
  }));
  filter();
})();
</script></html>"""

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

VIEWS = {"shopping", "shopping_add", "inventory", "actions", "add", "remove", "associate", "ticket", "photo", "product", "about"}
POST_VIEWS = {
    "barcode_add": "add",
    "barcode_associate": "associate",
    "barcode_remove_preview": "remove",
    "barcode_remove": "remove",
    "barcode_photo": "photo",
    "product_update": "product",
    "product_photo": "product",
    "product_barcode_add": "product",
    "product_stock_save": "product",
    "shopping_add": "shopping",
    "shopping_toggle": "shopping",
    "shopping_remove": "shopping",
    "shopping_step": "inventory",
    "upload": "ticket",
    "preview": "ticket",
    "commit": "ticket",
}

def current_view():
    if request.endpoint == "index":
        candidate = request.args.get("view", "shopping")
    else:
        candidate = POST_VIEWS.get(request.endpoint, "shopping")
    return candidate if candidate in VIEWS else "shopping"

def render(message="", receipt=None, rid=None, simulation=None, can_commit=False, remove_candidate=None, photo=None, existing_product=None):
    view = current_view()
    inventory, inventory_error = [], False
    shopping, shopping_error = [], False
    shopping_product = None
    new_product_units = []
    if view == "add" and (INGRESS_MODE or session.get("auth")):
        try:
            new_product_units = barcode_stock.new_product_units()
        except Exception:
            pass
    if view == "shopping_add" and (INGRESS_MODE or session.get("auth")):
        try:
            shopping_product = barcode_stock.shopping_product_options(request.args.get("product_id"))
        except Exception:
            pass
    if view == "shopping" and (INGRESS_MODE or session.get("auth")):
        try:
            shopping = barcode_stock.shopping_list_snapshot()
        except Exception:
            shopping_error = True
    product = None
    if view == "product" and (INGRESS_MODE or session.get("auth")):
        pid = request.view_args.get("product_id") if request.view_args else request.args.get("product_id")
        try:
            product = barcode_stock.product_detail(pid)
        except (ValueError, TypeError, KeyError, barcode_stock.BarcodeError):
            pass
        except Exception:
            pass
    if view == "inventory" and (INGRESS_MODE or session.get("auth")):
        try:
            inventory = barcode_stock.inventory_with_shopping()
        except Exception:
            inventory_error = True
    return render_template_string(PAGE, csrf=csrf_token(), message=message,
                                  receipt=receipt, rid=rid, simulation=simulation,
                                  can_commit=can_commit, remove_candidate=remove_candidate, photo=photo,
                                  view=view, inventory=inventory, inventory_error=inventory_error,
                                  shopping=shopping, shopping_error=shopping_error,
                                  shopping_product=shopping_product,
                                  new_product_units=new_product_units,
                                  existing_product=existing_product,
                                  product=product,
                                  app_version=os.environ.get("DESPENSA_VERSION", "dev"),
                                  app_distribution=os.environ.get("DESPENSA_DISTRIBUTION", "Instalación de desarrollo"),
                                  grocy_configured=bool(os.environ.get("GROCY_URL") and os.environ.get("GROCY_API_KEY")),
                                  products=product_choices() if view == "associate" else [],
                                  authenticated=INGRESS_MODE or bool(session.get("auth")),
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

@app.post("/shopping/step/<int:product_id>/<direction>")
def shopping_step(product_id, direction):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        barcode_stock.change_shopping_quantity(product_id, direction)
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("Error de Grocy. Comprueba la cantidad de compra antes de reintentar."), 502
    finally:
        LOCK.release()
    return redirect(url_for("index", view="inventory"))


@app.post("/shopping/add/<int:product_id>")
def shopping_add(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        name = barcode_stock.add_to_shopping_list(product_id, request.form.get("amount"), request.form.get("unit_id"))
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("No se ha podido añadir el artículo. Comprueba la lista en Grocy antes de repetir."), 502
    finally:
        LOCK.release()
    return render(name + " añadido a la lista de la compra.")


@app.post("/shopping/<int:item_id>/toggle")
def shopping_toggle(item_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        barcode_stock.update_shopping_list_item(item_id, request.form.get("done") == "1")
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("No se pudo actualizar el artículo de compra."), 502
    finally:
        LOCK.release()
    return redirect(url_for("index", view="shopping"))


@app.post("/shopping/<int:item_id>/remove")
def shopping_remove(item_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        barcode_stock.remove_shopping_list_item(item_id)
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("No se pudo quitar el artículo de la lista."), 502
    finally:
        LOCK.release()
    return redirect(url_for("index", view="shopping"))


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

@app.post("/product/<int:product_id>/edit")
def product_update(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        result = barcode_stock.update_product_info(
            product_id, request.form.get("name"), request.form.get("pack_size"), request.form.get("unit_id"))
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("Error al actualizar el producto. Comprueba Grocy antes de reintentar."), 502
    finally:
        LOCK.release()
    return render("Producto actualizado: " + result["name"] + ". Existencias sin cambios.")


@app.post("/product/<int:product_id>/barcode")
def product_barcode_add(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        result = barcode_stock.associate_product_barcode(product_id, request.form.get("barcode", ""))
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("No se pudo asociar el código. Comprueba Grocy."), 502
    finally:
        LOCK.release()
    try:
        if not barcode_stock.product_detail(product_id)["image_url"]:
            found = product_images.lookup_image(request.form.get("barcode", ""))
            if found:
                barcode_stock.save_product_photo(product_id, found["image_url"])
    except Exception:
        pass  # Linking succeeded even when Open Food Facts is unavailable.
    return render("Código ya asociado." if result["already_linked"] else "Código asociado sin modificar existencias.")


@app.post("/product/<int:product_id>/stock-save")
def product_stock_save(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        adjustment = barcode_stock.prepare_stock_adjustment(
            product_id, request.form.get("desired_amount"), request.form.get("expected_amount"))
        applied = barcode_stock.apply_stock_adjustment(adjustment)
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 409
    except Exception:
        return render("Error de Grocy. Comprueba las existencias antes de reintentar."), 502
    finally:
        LOCK.release()
    return render("Stock actualizado: " + applied["after"] + ".")


@app.post("/product/<int:product_id>/photo")
def product_photo(product_id):
    try:
        product = barcode_stock.product_detail(product_id)
        if not product["barcodes"]:
            return render("Este producto no tiene códigos asociados."), 400
        photo = product_images.lookup_image(product["barcodes"][0])
    except Exception:
        return render("No se ha podido buscar la fotografía."), 502
    if not photo:
        return render("No se ha encontrado una foto para este producto.")
    try:
        barcode_stock.save_product_photo(product_id, photo["image_url"])
    except Exception:
        return render("Foto encontrada, pero no se pudo guardar en Grocy."), 502
    return render("Fotografía guardada en la ficha del producto.")


@app.get("/photo/lookup")
def photo_lookup():
    if not (INGRESS_MODE or session.get("auth")):
        abort(401)
    try:
        barcode = barcode_stock.validate_barcode(request.args.get("barcode", ""))
        found = product_images.lookup_image(barcode)
    except barcode_stock.BarcodeError:
        return jsonify({"image_url": None}), 400
    except Exception:
        return jsonify({"image_url": None}), 503
    return jsonify({"image_url": found["image_url"] if found else None})


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
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        result = barcode_stock.create_catalog_product(
            request.form.get("name"), request.form.get("barcode", ""),
            request.form.get("unit_id"), request.form.get("initial_stock", "0"),
            location_id=int(os.getenv("GROCY_LOCATION_ID", "2")),
            image_url=request.form.get("image_url"))
    except (barcode_stock.BarcodeError, ValueError) as exc:
        return render("No se pudo crear: " + str(exc)), 400
    except Exception:
        return render("Error de Grocy. Comprueba el catálogo antes de intentarlo otra vez."), 502
    finally:
        LOCK.release()
    if not result["created"]:
        return render("El producto ya existe.", existing_product={
            "id": result["product_id"], "name": result["name"]})
    return redirect(url_for("index", view="product", product_id=result["product_id"]))


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
    try:
        details = barcode_stock.grocy("GET", f"stock/products/{int(product['id'])}")
        unit_id = int(product["qu_id_stock"])
        units = barcode_stock.grocy("GET", "objects/quantity_units")
        unit = next((str(u["name"]) for u in units if int(u["id"]) == unit_id), "unidad")
        available = str(details.get("stock_amount", 0))
    except Exception:
        return render("No se pudo consultar el stock disponible."), 502
    session["remove_barcode"] = barcode
    return render(remove_candidate={"barcode": barcode, "name": product["name"],
                                    "available": available, "unit": unit})

@app.post("/barcode/remove")
def barcode_remove():
    barcode = request.form.get("barcode", "")
    if session.pop("remove_barcode", None) != barcode:
        abort(403, "Primero confirma el producto")
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        result = barcode_stock.consume_quantity(
            barcode, request.form.get("amount"), request.form.get("add_to_list") == "1")
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("Error de Grocy. Comprueba el stock antes de reintentar."), 502
    finally:
        LOCK.release()
    message = "Consumidos " + result["amount"] + " de " + result["name"] + "."
    if result["shopping_added"]:
        message += " Añadida la misma cantidad a la lista de la compra."
    elif result["shopping_error"]:
        message += " No se pudo añadir a la lista; el consumo SÍ se ha registrado. No repitas el consumo."
    return render(message)

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
