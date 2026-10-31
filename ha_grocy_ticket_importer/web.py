#!/usr/bin/env python3
"""Local-only prototype UI. NOT a Home Assistant ingress add-on."""
import hmac
import difflib
import unicodedata
import io
import urllib.request
import json
import os
import secrets
import subprocess
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template_string, request, session, url_for, send_file
from werkzeug.utils import secure_filename

import extract
import barcode_stock
import product_images
import variant_catalog
import catalog_audit
import shopping_match_queue

ROOT = Path(__file__).resolve().parent
load_dotenv(os.environ.get("GROCY_ENV_FILE", str(ROOT / ".env")))
DATA = Path(os.environ.get("RECEIPT_DATA_DIR", str(ROOT / "runtime" / "receipts")))
ALLOWED = {".pdf", ".jpg", ".jpeg", ".png"}
PHOTO_DIR = Path(os.environ.get("PRODUCT_IMAGE_DIR", str(ROOT / "runtime" / "product_images")))
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
.product-photo-hero{display:flex;flex-direction:column;align-items:center;gap:10px;padding:16px;border:1px solid var(--line);border-radius:16px;margin:12px 0 22px;background:var(--surface,#fff)}
.product-photo-hero .photo-preview{width:100%;display:flex;flex-direction:column;align-items:center}
.product-photo-hero img:not([hidden]){max-width:200px;max-height:180px;object-fit:contain;border-radius:12px}
.product-photo-hero button{max-width:280px}
.product-sheet h3{margin-top:24px;margin-bottom:8px}
.product-danger-zone{margin-top:28px;padding:12px;border-top:1px solid var(--line)}
.product-danger-zone summary{cursor:pointer;font-size:.9rem}
.ticket-review-item{border-bottom:1px solid var(--line);padding:14px 0}
.ticket-review-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media(max-width:520px){.ticket-review-fields{grid-template-columns:1fr}}
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
.shopping-stepper[data-busy="true"]{opacity:.65}
.shopping-stepper[hidden],.shopping-cart-form[hidden]{display:none!important}
.shopping-cart-form{margin:0;width:100%}
.shopping-cart-form button{width:100%;margin:0;min-height:41px;background:var(--soft);color:var(--primary-dark);border:1px solid #b9d8c6;border-radius:11px;font-weight:750;padding:7px 9px}
.shopping-cart-form button:hover{background:#d3e9dc;color:var(--primary-dark)}
.shopping-quick[data-busy="true"]{opacity:.65}
.shopping-quick{display:flex;flex-direction:column;gap:3px}
.shopping-quick .shopping-stepper{width:100%}
.shopping-stepper-message{grid-column:1/-1;font-size:.7rem;color:var(--danger);margin:0;line-height:1.3}
.shopping-stepper-message:empty{display:none}
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
.shopping-list-row{display:grid;grid-template-columns:minmax(0,1fr) 220px;align-items:center;gap:12px}
.shopping-list-product{min-width:0;overflow-wrap:anywhere}
.shopping-list-product strong{overflow-wrap:anywhere}
.shopping-controls{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:6px;align-items:center;min-width:0}
.shopping-controls form{margin:0;min-width:0}
.shopping-controls button[type=submit]{display:flex;align-items:center;justify-content:center;width:100%;min-width:0;min-height:42px;margin:0;padding:7px 5px;line-height:1.2;font-size:.80rem;text-align:center;white-space:normal}
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
 .shopping-list-row{grid-template-columns:minmax(0,1fr) 106px;align-items:center;gap:8px}
 .shopping-list-row .product-thumb{width:40px;height:40px}
 .shopping-list-product{gap:7px}
 .shopping-controls{grid-template-columns:1fr;gap:5px}
 .shopping-controls button[type=submit]{min-height:35px;padding:5px 3px;font-size:.73rem;border-radius:9px;min-width:0}
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
{% if pending_matches_error %}<p role="alert">No se pudieron cargar las sugerencias de Alexa.</p>{% endif %}
<section id="shopping-live-section"><button type="button" id="shopping-refresh" class="scan-trigger" style="float:right">↻ Actualizar</button><p class="section-eyebrow">Sincronizada con Grocy</p><h2>🛒 Lista de la compra</h2>
{% if shopping_error %}<p role="alert">No se pudo cargar la lista desde Grocy.</p>{% else %}
<p>{{ shopping|length }} artículos en la lista. Marcarlos como comprados no añade stock automáticamente.</p>
{% if not shopping %}<p>Tu lista está vacía. Añade un artículo desde Mi despensa.</p>{% endif %}
{% if shopping|selectattr("done")|list|length %}<form method="post" action="{{ url_for('shopping_clear_completed') }}" onsubmit="return confirm('¿Eliminar todos los artículos marcados como comprados?')"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit" class="scan-trigger">🗑 Eliminar comprados ({{ shopping|selectattr("done")|list|length }})</button></form>{% endif %}
<div class="inventory-list">
{% for item in shopping %}
<article class="inventory-row shopping-list-row">
<div class="product-name-with-photo shopping-list-product">{% if item.image_url %}<img class="product-thumb" src="{{ item.image_url }}" alt="" loading="lazy" referrerpolicy="no-referrer">{% endif %}<div><strong {% if item.done %}style="text-decoration:line-through;opacity:.6"{% endif %}>{% if item.product_id %}<a class="product-detail-link" href="{{ url_for('index', view='product', product_id=item.product_id) }}">{{ item.name }} →</a>{% else %}{{ item.name }}{% endif %}</strong><small>{{ item.amount }} {{ item.unit }}</small></div></div>
<div class="shopping-controls">
<form method="post" action="{{ url_for('shopping_toggle', item_id=item.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="done" value="{{ '0' if item.done else '1' }}">
<button type="submit" class="scan-trigger">{{ '↩ Pendiente' if item.done else '✓ Comprado' }}</button></form>
<form method="post" action="{{ url_for('shopping_remove', item_id=item.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit" class="scan-trigger">✕ Quitar</button></form>
</div>

{% if item.alexa_match %}<details class="ticket-review-item alexa-inline-match"><summary>🔔 Elegir producto para «{{ item.alexa_match.name }}»</summary>
<form method="post" action="{{ url_for('alexa_match_choose') }}">
<input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="key" value="{{ item.alexa_match.key }}">
<label>Producto genérico propuesto<select name="product_id" required>
<option value="">Selecciona manualmente</option>
{% for candidate in item.alexa_match.candidates %}<option value="{{ candidate.id }}" {% if candidate.id == item.alexa_match.selected_product_id %}selected{% endif %}>{{ candidate.name }}</option>{% endfor %}
</select></label><button type="submit">Guardar elección</button></form>
</details>{% endif %}
</article>
{% endfor %}
{% for match in pending_matches if match.key not in shopping_match_keys %}
<article class="inventory-row"><div class="shopping-list-product"><strong>{{ match.name }}</strong><small>Artículo pendiente de Alexa</small></div>
<details class="ticket-review-item alexa-inline-match"><summary>🔔 Elegir producto</summary>
<form method="post" action="{{ url_for('alexa_match_choose') }}">
<input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="key" value="{{ match.key }}">
<label>Producto genérico propuesto<select name="product_id" required>
<option value="">Selecciona manualmente</option>
{% for candidate in match.candidates %}<option value="{{ candidate.id }}" {% if candidate.id == match.selected_product_id %}selected{% endif %}>{{ candidate.name }}</option>{% endfor %}
</select></label><button type="submit">Guardar elección</button></form>
</details></article>
{% endfor %}
</div>{% endif %}
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
<label for="inventory-search">Buscar por nombre o código de barras</label><div class="barcode-input-row"><input id="inventory-search" data-lookup-url="{{ url_for('inventory_barcode_lookup') }}" type="search" autocomplete="off" placeholder="Nombre o código EAN / UPC"><button type="button" class="scan-trigger" data-scan-input="inventory-search">📷 Escanear</button></div><p id="inventory-barcode-status" role="status" aria-live="polite"></p><div class="inventory-list" id="inventory-list">
{% for p in inventory %}
<article class="inventory-row pantry-row" data-name="{{ p.name }}" data-product-id="{{ p.id }}">
<div class="pantry-info product-name-with-photo">{% if p.image_url %}<img class="product-thumb" src="{{ p.image_url }}" alt="" loading="lazy" referrerpolicy="no-referrer">{% endif %}<a class="product-detail-link" href="{{ url_for('index', view='product', product_id=p.id) }}"><strong>{{ p.name }}</strong><small>Ficha →</small></a></div>
<div class="pantry-side">
<div class="inventory-quantity">{% if p.amount is none %}<span class="quantity-unknown">Sin datos</span>{% else %}<strong>{{ p.amount }}</strong><small>{{ p.unit }}</small>{% endif %}</div>
<div class="shopping-quick" data-busy="false">
<form class="shopping-cart-form" method="post" action="{{ url_for('shopping_step', product_id=p.id, direction='plus') }}" {% if p.shopping_can_subtract %}hidden{% endif %}>
<input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit" aria-label="Añadir {{ p.name }} a la lista de la compra">🛒 Añadir</button></form>
<div class="shopping-stepper" aria-label="Cantidad de {{ p.name }} en lista de compra" {% if not p.shopping_can_subtract %}hidden{% endif %}>
<form method="post" action="{{ url_for('shopping_step', product_id=p.id, direction='minus') }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="minus" type="submit" aria-label="Quitar {{ p.shopping_step }} {{ p.shopping_unit }} de {{ p.name }}">−</button></form>
<output><span class="shopping-amount">{{ p.shopping_amount }}</span><small>{{ p.shopping_unit }}</small></output>
<form method="post" action="{{ url_for('shopping_step', product_id=p.id, direction='plus') }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit" aria-label="Añadir {{ p.shopping_step }} {{ p.shopping_unit }} de {{ p.name }}">+</button></form>
</div><p class="shopping-stepper-message" role="status" aria-live="polite"></p></div></div>
</article>
{% endfor %}
</div><p id="inventory-empty" hidden>No hay productos que coincidan con la búsqueda.</p>
{% endif %}
</section>
{% elif view == 'actions' %}
<div class="hero"><strong>¿Qué quieres hacer?</strong><p>Elige una operación. Cada una tiene su propia pantalla.</p>
<nav class="action-grid" aria-label="Acciones de Despensa">
<a class="action-link" href="{{ url_for('index', view='add') }}"><span aria-hidden="true">➕</span><strong>Añadir producto</strong><small>Crear artículo nuevo</small></a>
<a class="action-link" href="{{ url_for('index', view='ticket') }}"><span aria-hidden="true">🧾</span><strong>Subir ticket</strong><small>Importar compra</small></a>
<a class="action-link" href="{{ url_for('index', view='duplicates') }}"><span aria-hidden="true">🔎</span><strong>Detectar duplicados</strong><small>Revisar artículos similares</small></a>
<a class="action-link" href="{{ url_for('index', view='alexa_matches') }}"><span aria-hidden="true">🗣️</span><strong>Coincidencias Alexa</strong><small>Revisar nombres ambiguos</small></a>
</nav></div>
{% else %}
<p><a class="back-link" href="{{ url_for('index', view='inventory') if view == 'product' else url_for('index', view='actions') }}">← {{ 'Volver a mi despensa' if view == 'product' else 'Volver a acciones' }}</a></p>
{% endif %}
{% if view == 'alexa_matches' %}
<section><p class="section-eyebrow">Alexa · Revisión segura</p><h2>Coincidencias pendientes</h2>
<p class="helper">Se conservan los nombres originales de Alexa y las notas de Grocy. Elegir un producto guarda una propuesta. Si la sincronización está activada, se usará solo cuando no haya conflictos; nunca convierte notas existentes ni modifica existencias.</p>
{% if pending_matches_error %}<p role="alert">No se pudo leer la cola de coincidencias.</p>
{% elif not pending_matches %}<p>No hay coincidencias ambiguas pendientes. La lista se analiza cuando está activa la sincronización con Alexa.</p>
{% else %}
{% for match in pending_matches %}
<div class="ticket-review-item"><strong>{{ match.name }}</strong>
{% if match.selection_stale %}<p role="alert">La propuesta anterior ya no es válida. Selecciona de nuevo un producto antes de sincronizar.</p>{% endif %}
<form method="post" action="{{ url_for('alexa_match_choose') }}">
<input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="key" value="{{ match.key }}">
<label>Producto genérico propuesto<select name="product_id" required>
<option value="">Selecciona manualmente</option>
{% for candidate in match.candidates %}<option value="{{ candidate.id }}" {% if candidate.id == match.selected_product_id %}selected{% endif %}>{{ candidate.name }}</option>{% endfor %}
</select></label><button type="submit">Guardar propuesta sin cambiar listas</button></form>
{% if match.selected_product_id %}<p class="helper">Propuesta guardada. Se conserva el nombre original de Alexa; la sincronización aplicará la identidad solo si supera las comprobaciones.</p>{% endif %}
</div>
{% endfor %}{% endif %}
</section>
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
<p class="section-eyebrow">Editar artículo</p>
<h2>{{ product.name }}</h2>
<p class="helper">Actualiza los datos y guarda todos los cambios de una vez.</p>
<div class="product-photo-hero"><div class="photo-preview"><img id="product-photo-display" {% if product.image_url %}src="{{ product.image_url }}"{% else %}hidden{% endif %} alt="Imagen del producto {{ product.name }}" loading="lazy" referrerpolicy="no-referrer"><p id="product-photo-status" class="helper" aria-live="polite"></p></div>
<button type="button" id="product-camera-open">📷 {{ "Cambiar foto" if product.image_url else "Hacer foto" }}</button></div>
<div id="product-camera-panel" hidden><video id="product-camera-video" autoplay playsinline muted style="width:100%;max-height:420px"></video><button type="button" id="product-camera-snapshot">Capturar foto</button><button type="button" id="product-camera-close">Cancelar</button></div>
{% if not product.image_url and product.barcodes %}<div id="product-photo-autoload" data-barcode="{{ product.barcodes[0] }}" data-save-url="{{ url_for('product_photo_save', product_id=product.id) }}" data-csrf="{{ csrf }}"></div>{% endif %}
<form id="product-edit-form" method="post" action="{{ url_for('product_edit_all', product_id=product.id) }}" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input id="product-photo-upload" name="photo" type="file" accept="image/jpeg" hidden>
<h3>Datos del artículo</h3><label for="edit-product-name">Nombre del artículo</label><input id="edit-product-name" name="name" maxlength="200" value="{{ product.name }}" required>
<label for="edit-unit">Unidad de medida</label><select id="edit-unit" name="unit_id" required>
{% for u in product.units if u.name|lower in ("piece", "pieces", "unidad", "unidades", "kg", "kilogram", "kilogramo", "kilogramos") %}<option value="{{ u.id }}" {% if u.id == product.purchase_unit_id %}selected{% endif %}>{{ u.name }}</option>{% endfor %}</select>
<h3>Existencias</h3>
<input type="hidden" name="expected_amount" value="{{ product.stock_amount }}">
<label for="edit-stock-amount">Cantidad total que tengo</label><input id="edit-stock-amount" name="desired_amount" inputmode="decimal" type="number" step="0.01" min="0" value="{{ product.stock_amount }}" required>
<h3>Identificación</h3>
{% if product.barcodes %}<label for="old-product-barcode">Código actual</label><input id="old-product-barcode" name="old_barcode" value="{{ product.barcodes[0] }}" inputmode="numeric" pattern="[0-9]{8,14}">{% endif %}
<label for="edit-barcode">Nuevo código (opcional)</label><span class="barcode-input-row"><input id="edit-barcode" name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" autocomplete="off" placeholder="Escanear o escribir"><button class="scan-trigger" type="button" data-scan-input="edit-barcode" aria-label="Escanear nuevo código de barras con la cámara">📷 Escanear</button></span>
<p class="helper">Solo se modificará el código de barras si introduces uno nuevo.</p>
<button id="product-save-all" type="submit">Guardar cambios</button>
</form>
<h3>Variantes por supermercado</h3>
<p class="helper">Todas las variantes comparten las existencias de este producto genérico en Grocy. No se fusionan artículos ni se modifican cantidades.</p>
{% if variants_error %}<p role="alert">No se pudieron consultar las variantes guardadas.</p>{% endif %}
{% if variants %}
<div class="inventory-list">{% for v in variants %}
<div class="inventory-row"><div class="pantry-info"><strong>{{ v.name }}</strong><small>{{ v.brand }}{% if v.brand and v.supermarket %} · {% endif %}{{ v.supermarket }}</small><small>Código: {{ v.barcode }} · Unidades por compra: {{ v.units_per_purchase }}</small></div></div>
{% endfor %}</div>
{% else %}<p class="helper">Aún no hay variantes asociadas.</p>{% endif %}
<form method="post" action="{{ url_for('product_variant_add', product_id=product.id) }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label for="variant-name">Nombre de la variante</label><input id="variant-name" name="name" maxlength="200" required placeholder="Leche entera Hacendado">
<label for="variant-barcode">Código de barras</label><span class="barcode-input-row"><input id="variant-barcode" name="barcode" inputmode="numeric" pattern="[0-9]{8,14}" required autocomplete="off"><button type="button" class="scan-trigger" data-scan-input="variant-barcode">📷 Escanear</button></span>
<label for="variant-supermarket">Supermercado</label><input id="variant-supermarket" name="supermarket" maxlength="120" placeholder="Mercadona">
<label for="variant-brand">Marca</label><input id="variant-brand" name="brand" maxlength="120" placeholder="Hacendado">
<label for="variant-factor">Unidades por compra (solo metadatos)</label><input id="variant-factor" name="units_per_purchase" type="number" min="0.01" max="999999" step="0.01" value="1" required>
<p class="helper">Se comprobará que el código no pertenezca a otro producto de Grocy. El factor no cambia las conversiones de stock existentes.</p>
<button type="submit">Guardar variante sin cambiar stock</button>
</form>
<details class="product-danger-zone"><summary>Opciones avanzadas · Eliminar artículo</summary><h3>Eliminar artículo</h3>
<p class="helper">Al confirmar, las existencias se descontarán hasta cero y después se eliminará el artículo definitivamente. Esta operación no se puede deshacer.</p>
<form method="post" action="{{ url_for('product_delete', product_id=product.id) }}" onsubmit="return confirm('¿Confirmas poner sus existencias a cero y eliminar definitivamente este artículo de Grocy?');">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input type="hidden" name="expected_name" value="{{ product.name }}">
<button type="submit">🗑️ Eliminar artículo</button>
</form></details>
{% else %}<p role="alert">No se ha podido cargar la ficha del producto.</p>{% endif %}
</section>
{% endif %}
{% if view == 'duplicates' %}
<section><p class="section-eyebrow">Catálogo · Solo lectura</p><h2>🔎 Posibles duplicados</h2>
<p>Compara códigos de barras y nombres. No se modifica ni elimina ningún artículo.</p>
<p><a class="back-link" href="{{ url_for('download_catalog_audit') }}">⬇ Descargar auditoría completa de Grocy (JSON)</a></p>
{% if duplicates_error %}<p role="alert">No se ha podido consultar el catálogo de Grocy.</p>
{% elif not duplicates %}<p>Sin posibles duplicados detectados.</p>
{% else %}<p>{{ duplicates|length }} grupos para revisar.</p>
{% for group in duplicates %}<div class="ticket-review-item"><strong>{{ group.reason }}</strong>
{% for item in group['items'] %}<p><a href="{{ url_for('index', view='product', product_id=item.id) }}">{{ item.name }}</a> <small>· ID {{ item.id }}{% if item.barcodes %} · {{ item.barcodes|join(', ') }}{% endif %}</small></p>{% endfor %}</div>{% endfor %}{% endif %}
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
<label for="new-product-unit">Unidad de compra</label>
<select id="new-product-unit" name="unit_id" required>
{% for u in new_product_units %}<option value="{{ u.id }}" {% if u.name|lower in ('piece','unidad','unidades') %}selected{% endif %}>{{ u.name }}</option>{% endfor %}
</select>
<div id="new-pack-fields" hidden>
<label for="new-pack-size">Piezas por pack</label>
<input id="new-pack-size" name="pack_size" type="number" min="1" max="1000" step="1" value="1">
<p class="helper">Si compras 2 packs de 5, se guardarán 10 Piece en el inventario.</p>
</div>
<label for="new-product-stock">Cantidad inicial (en la unidad elegida)</label>
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
{% if view == 'ticket' %}
<section id="ticket"><p class="section-eyebrow">Compras</p><h2>Subir ticket</h2><p>PDF, JPG o PNG (máximo 12 MiB). La subida no modifica Grocy.</p>
<form id="ticket-upload-form" method="post" action="{{ url_for('upload') }}" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="{{ csrf }}">
<button type="button" id="ticket-live-camera">📷 Abrir cámara</button>
<div id="ticket-camera-panel" hidden><video id="ticket-video" autoplay playsinline muted style="width:100%;max-height:420px"></video><button type="button" id="ticket-snapshot">Capturar foto</button><button type="button" id="ticket-camera-close">Cancelar</button></div>
<input id="ticket-camera" type="file" name="ticket" accept="image/*" style="position:absolute;width:1px;height:1px;opacity:0" tabindex="-1">
<label for="ticket-file" class="scan-trigger" style="display:inline-block;padding:12px;cursor:pointer">📁 Elegir PDF o imagen existente</label>
<input id="ticket-file" type="file" name="ticket" accept=".pdf,.jpg,.jpeg,.png" style="position:absolute;width:1px;height:1px;opacity:0" tabindex="-1">
<p class="helper" id="ticket-selection-status" role="status">Pulsa «Abrir cámara» para hacer una foto o «Elegir archivo» para adjuntar un documento.</p>
<button id="ticket-upload-submit" type="submit">Extraer y revisar</button><p id="ticket-upload-progress" class="helper" role="status" aria-live="polite" hidden>⏳ Procesando ticket… Puede tardar unos segundos.</p></form></section>
{% if receipt %}
<section><h2>{{ receipt.merchant }} · {{ receipt.receipt_date }} · {{ receipt.total }} €</h2>
<p>{{ receipt['items']|length }} líneas. Las marcadas como revisión se omitirán al importar.</p>
<p>Revisa las unidades compradas. Si es un pack, indica cuántas piezas contiene; guardaremos esa conversión para próximas compras.</p>
<form method="post" action="{{ url_for('preview', rid=rid) }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
{% for item in receipt['items'] %}
<div class="ticket-review-item">
<label>Nombre del artículo<input id="ticket-item-name-{{ loop.index0 }}" name="item_name_{{ loop.index0 }}" maxlength="200" value="{{ item.name }}" required></label>
{% if suggestions and suggestions[loop.index0] %}<label>Posibles coincidencias en tu despensa<select class="ticket-match-select" data-target="ticket-item-name-{{ loop.index0 }}"><option value="">Mantener nombre del ticket / escribir otro</option>{% for candidate in suggestions[loop.index0] %}<option value="{{ candidate.name }}">{{ candidate.name }}</option>{% endfor %}</select></label><p class="helper">Selecciona un artículo existente para reutilizarlo; no se selecciona automáticamente.</p>{% endif %}
<p>{{ item.quantity }} × {{ item.unit_price }} € · {{ 'Revisión necesaria: ' + item.reason if item.ambiguous else 'Propuesto' }}</p>
<div class="ticket-review-fields">
<label>Unidades compradas
<input name="purchase_units_{{ loop.index0 }}" type="number" min="0.01" step="0.01" value="{{ item.get('purchase_units', item.quantity) }}" required></label>
<label>Piezas por envase (1 = individual)
<input name="pieces_per_pack_{{ loop.index0 }}" type="number" min="1" max="1000" step="1" value="{{ item.get('pieces_per_pack', 1) }}" required></label>
</div>
</div>
{% endfor %}
<button type="submit">Guardar cantidades y simular</button></form>
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
<dialog id="scanner-dialog" aria-labelledby="scanner-title" data-photo-lookup-url="{{ url_for('photo_lookup') }}">
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
  // The cart becomes a +/- control on the first successful addition.
  // Reverting to zero restores the cart without navigation or scroll jumps.
  document.querySelectorAll('.shopping-quick').forEach(control => {
    const cart = control.querySelector('.shopping-cart-form');
    const stepper = control.querySelector('.shopping-stepper');
    const buttons = Array.from(control.querySelectorAll('button[type="submit"]'));
    const value = control.querySelector('.shopping-amount');
    const message = control.querySelector('.shopping-stepper-message');
    function showQuantity(amount) {
      const quantity = Number(amount);
      if (!Number.isFinite(quantity) || quantity < 0) return;
      if (value) value.textContent = amount;
      const inList = quantity > 0;
      if (cart) cart.hidden = inList;
      if (stepper) stepper.hidden = !inList;
    }
    control.querySelectorAll('form').forEach(form => {
      form.addEventListener('submit', async event => {
        if (!window.fetch || !window.FormData) return; // Regular form fallback
        event.preventDefault();
        if (control.dataset.busy === 'true') return;
        control.dataset.busy = 'true';
        buttons.forEach(button => { button.disabled = true; });
        if (message) message.textContent = '';
        try {
          const response = await fetch(form.action, {
            method: 'POST', credentials: 'same-origin',
            headers: {'Accept': 'application/json'},
            body: new FormData(form)
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'No se pudo modificar la lista.');
          showQuantity(result.amount);
        } catch (error) {
          if (message) message.textContent =
            error.message || 'Error de conexión. Comprueba la lista antes de reintentar.';
        } finally {
          control.dataset.busy = 'false';
          buttons.forEach(button => { button.disabled = false; });
        }
      });
    });
  });
  const productAuto = document.getElementById('product-photo-autoload');
  if (productAuto) {
    const statusNode = document.getElementById('product-photo-status');
    const imageNode = document.getElementById('product-photo-display');
    const payload = new URLSearchParams({
      barcode: productAuto.dataset.barcode, csrf: productAuto.dataset.csrf
    });
    fetch(productAuto.dataset.saveUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: payload.toString()
    }).then(r => r.ok ? r.json() : null).then(result => {
      if (result?.saved && imageNode) {
        imageNode.src = result.image_url;
        imageNode.hidden = false;
        if (statusNode) statusNode.textContent = 'Imagen guardada desde Open Food Facts.';
      }
    }).catch(() => {});
  }
  const newUnitSelector = document.getElementById('new-product-unit');
  const newPackFields = document.getElementById('new-pack-fields');
  if (newUnitSelector && newPackFields) {
    const updateNewPack = () => {
      const pack = (newUnitSelector.selectedOptions[0]?.textContent || '').toLowerCase().includes('pack');
      newPackFields.hidden = !pack;
      const input = document.getElementById('new-pack-size');
      if (input) input.required = pack;
    };
    newUnitSelector.addEventListener('change', updateNewPack);
    updateNewPack();
  }
  const unitSelector = document.getElementById('edit-unit');
  const packFields = document.getElementById('pack-size-fields');
  if (unitSelector && packFields) {
    const updatePackFields = () => {
      const label = unitSelector.selectedOptions[0]?.textContent?.trim().toLowerCase() || '';
      packFields.hidden = !label.includes('pack');
      const packInput = document.getElementById('edit-pack-size');
      if (packInput) packInput.required = !packFields.hidden;
    };
    unitSelector.addEventListener('change', updatePackFields);
    updatePackFields();
  }
  // Scanning or typing a complete EAN/UPC previews an image automatically.
  document.querySelectorAll('form input[name="barcode"]').forEach(input => {
    const form = input.closest('form');
    const preview = form?.querySelector('.barcode-photo-preview');
    const status = form?.querySelector('.photo-status');
    const hidden = form?.querySelector('.barcode-image-url');
    const nameInput = form?.querySelector('#new-product-name');
    let suggestedName = '';
    if (!preview) return;
    let sequence = 0;
    async function loadPhoto() {
      const id = ++sequence;
      const barcode = input.value.trim();
      if (nameInput && nameInput.value === suggestedName) nameInput.value = '';
      suggestedName = '';
      if (hidden) hidden.value = '';
      preview.hidden = true;
      preview.removeAttribute('src');
      if (!/^\\d{8,14}$/.test(barcode)) {
        if (status) status.textContent = '';
        return;
      }
      if (status) status.textContent = 'Buscando foto automáticamente…';
      try {
        const url = new URL(dialog.dataset.photoLookupUrl, window.location.href);
        url.searchParams.set('barcode', barcode);
        const response = await fetch(url.toString(), {credentials:'same-origin'});
        if (!response.ok) throw new Error('lookup');
        const data = await response.json();
        if (sequence !== id) return;
        if (nameInput && data.name && !nameInput.value.trim()) {
          suggestedName = data.name;
          nameInput.value = data.name;
        }
        if (data.image_url) {
          preview.src = data.image_url;
          preview.hidden = false;
          if (hidden) hidden.value = data.image_url;
          if (status) status.textContent = 'Foto encontrada en Open Food Facts.';
        } else if (status) status.textContent = data.name ? 'Nombre encontrado en Open Food Facts; sin foto disponible.' : 'No hay información para este código.';
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
      const input = button.dataset.scanInput ? document.getElementById(button.dataset.scanInput) : button.closest('form')?.querySelector('input[name="barcode"]');
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
  const open = document.getElementById('ticket-live-camera');
  const panel = document.getElementById('ticket-camera-panel');
  const video = document.getElementById('ticket-video');
  let stream = null;
  function stop() { if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; if(panel) panel.hidden = true; }
  if (open && panel && video) {
    open.addEventListener('click', async () => {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error('Cámara web no disponible');
        stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}},audio:false});
        video.srcObject = stream;
        panel.hidden = false;
      } catch(e) { stop(); const status = document.getElementById('ticket-selection-status'); if(status) status.textContent = 'No se pudo abrir la cámara aquí. Prueba desde un navegador externo o utiliza Elegir archivo.'; }
    });
    document.getElementById('ticket-camera-close').addEventListener('click', stop);
    document.getElementById('ticket-snapshot').addEventListener('click', () => {
      if (!stream || !video.videoWidth) return;
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video,0,0);
      canvas.toBlob(blob => {
        if (!blob) return;
        const input = document.getElementById('ticket-camera');
        const dt = new DataTransfer();
        dt.items.add(new File([blob], 'ticket.jpg', {type:'image/jpeg'}));
        input.files = dt.files;
        const existing = document.getElementById('ticket-file'); if(existing) existing.value = '';
        const status = document.getElementById('ticket-selection-status'); if(status) status.textContent = 'Foto capturada. Pulsa Extraer y revisar.';
        stop();
      },'image/jpeg',0.88);
    });
    window.addEventListener('pagehide', stop);
  }
  document.querySelectorAll('.ticket-match-select').forEach(select => select.addEventListener('change', () => { const input = document.getElementById(select.dataset.target); if(input && select.value) input.value = select.value; }));
  const productOpen = document.getElementById('product-camera-open');
  if (productOpen) {
    const panel = document.getElementById('product-camera-panel');
    const video = document.getElementById('product-camera-video');
    let productStream = null;
    const closeProductCamera = () => { if (productStream) productStream.getTracks().forEach(t => t.stop()); productStream = null; panel.hidden = true; };
    productOpen.addEventListener('click', async () => {
      try {
        productStream = await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}},audio:false});
        video.srcObject = productStream; panel.hidden = false;
      } catch(e) { const status = document.getElementById('product-photo-status'); if(status) status.textContent = 'No se pudo abrir la cámara. Comprueba los permisos.'; }
    });
    document.getElementById('product-camera-close').addEventListener('click', closeProductCamera);
    document.getElementById('product-camera-snapshot').addEventListener('click', () => {
      if (!productStream || !video.videoWidth) return;
      const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0);
      canvas.toBlob(blob => {
        if (!blob) return;
        const dt = new DataTransfer(); dt.items.add(new File([blob], 'producto.jpg', {type:'image/jpeg'}));
        document.getElementById('product-photo-upload').files = dt.files;
        const image = document.getElementById('product-photo-display');
        if (image) { image.src = URL.createObjectURL(blob); image.hidden = false; }
        const status = document.getElementById('product-photo-status'); if(status) status.textContent = 'Foto capturada. Pulsa Guardar cambios.';
        closeProductCamera();
      }, 'image/jpeg', 0.88);
    });
    window.addEventListener('pagehide', closeProductCamera);
  }
  const uploadForm = document.getElementById('ticket-upload-form');
  if (uploadForm) {
    let submitting = false;
    uploadForm.addEventListener('submit', event => {
      if (submitting) { event.preventDefault(); return; }
      const cameraInput = document.getElementById('ticket-camera');
      const fileInput = document.getElementById('ticket-file');
      if (!(cameraInput && cameraInput.files.length) && !(fileInput && fileInput.files.length)) {
        event.preventDefault();
        const status = document.getElementById('ticket-selection-status');
        if (status) status.textContent = 'Haz una foto o selecciona un archivo antes de continuar.';
        return;
      }
      submitting = true;
      const button = document.getElementById('ticket-upload-submit');
      if (button) { button.disabled = true; button.textContent = '⏳ Extrayendo…'; button.setAttribute('aria-busy', 'true'); }
      const progress = document.getElementById('ticket-upload-progress');
      if (progress) progress.hidden = false;
    });
    window.addEventListener('pageshow', () => {
      submitting = false;
      const button = document.getElementById('ticket-upload-submit');
      if (button) { button.disabled = false; button.textContent = 'Extraer y revisar'; button.removeAttribute('aria-busy'); }
      const progress = document.getElementById('ticket-upload-progress');
      if (progress) progress.hidden = true;
    });
  }
  const camera = document.getElementById('ticket-camera');
  const file = document.getElementById('ticket-file');
  if (!camera || !file) return;
  const status = document.getElementById('ticket-selection-status');
  camera.addEventListener('change', () => {
    if (camera.files.length) { file.value = ''; status.textContent = 'Foto seleccionada: ' + camera.files[0].name; }
  });
  file.addEventListener('change', () => {
    if (file.files.length) { camera.value = ''; status.textContent = 'Archivo seleccionado: ' + file.files[0].name; }
  });
})();
</script>

<script>
(() => {
  const section = document.getElementById('shopping-live-section');
  if (!section) return;
  let pending = false;
  let previous = section.innerHTML;
  let touchStart = null;
  section.addEventListener('click', event => {
    if (event.target.closest('#shopping-refresh')) refresh();
  });
  document.addEventListener('touchstart', e => {
    if (window.scrollY <= 5 && e.touches.length === 1) touchStart = e.touches[0].clientY;
    else touchStart = null;
  }, {passive: true});
  document.addEventListener('touchend', e => {
    if (touchStart !== null && window.scrollY <= 5 && e.changedTouches[0].clientY - touchStart > 90) refresh();
    touchStart = null;
  }, {passive: true});
  async function refresh() {
    if (pending || document.hidden || section.querySelector('form:focus-within')) return;
    pending = true;
    const button = section.querySelector('#shopping-refresh');
    if (!button) { pending = false; return; }
    button.disabled = true;
    button.textContent = 'Actualizando…';
    try {
      const response = await fetch(window.location.href, {credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'text/html'}});
      if (!response.ok) return;
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const updated = doc.getElementById('shopping-live-section');
      if (!updated) return;
      const next = updated.innerHTML;
      if (next !== previous) {
        section.innerHTML = next;
        previous = next;
      }
    } catch (_) {
      // Keep the current list on transient network errors.
    } finally {
      pending = false;
      const currentButton = section.querySelector('#shopping-refresh');
      if (currentButton) {
        currentButton.disabled = false;
        currentButton.textContent = '↻ Actualizar';
      }
    }
  }
  setInterval(refresh, 10000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
</script>
<script>
(() => {
  const search = document.getElementById('inventory-search');
  if (!search) return;
  const items = Array.from(document.querySelectorAll('.inventory-row'));
  const empty = document.getElementById('inventory-empty');
  const status = document.getElementById('inventory-barcode-status');
  const norm = value => value.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLocaleLowerCase('es');
  let lookupToken = 0;
  async function update() {
    const query = norm(search.value.trim());
    const token = ++lookupToken;
    let matchingId = null;
    if (/^\\d{8,14}$/.test(query)) {
      status.textContent = 'Buscando código…';
      try {
        const response = await fetch(search.dataset.lookupUrl + '?barcode=' + encodeURIComponent(query), {credentials:'same-origin'});
        const result = await response.json();
        if (token !== lookupToken) return;
        if (response.ok && result.product_id) matchingId = String(result.product_id);
        status.textContent = matchingId ? '' : (result.error || 'Código no encontrado.');
      } catch (_) { if (token !== lookupToken) return; status.textContent = 'No se pudo consultar el código.'; }
    } else { status.textContent = ''; }
    let count = 0;
    for (const item of items) {
      const nameMatch = norm(item.dataset.name || '').includes(query);
      const show = matchingId ? item.dataset.productId === matchingId : (/^\\d{8,14}$/.test(query) ? false : nameMatch);
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
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        token = session.get("csrf")
        if not token or not hmac.compare_digest((request.headers.get("X-CSRF-Token", "") if request.path.startswith("/api/v1/") else request.form.get("csrf", "")), token):
            abort(403)
    if request.endpoint not in ("index", "login", "static") and not (INGRESS_MODE or session.get("auth")):
        abort(401)

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]

VIEWS = {"shopping", "shopping_add", "inventory", "actions", "add", "remove", "associate", "ticket", "photo", "product", "about", "duplicates", "alexa_matches"}
POST_VIEWS = {
    "barcode_add": "add",
    "barcode_associate": "associate",
    "barcode_remove_preview": "remove",
    "barcode_remove": "remove",
    "barcode_photo": "photo",
    "product_update": "product",
    "product_delete": "product",
    "product_photo": "product",
    "product_barcode_add": "product",
    "product_variant_add": "product",
    "alexa_match_choose": "alexa_matches",
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

def detect_duplicates():
    """Read-only candidate groups; never merge catalog entries automatically."""
    products = barcode_stock.grocy("GET", "objects/products")
    codes = barcode_stock.grocy("GET", "objects/product_barcodes")
    if not isinstance(products, list) or not isinstance(codes, list):
        raise ValueError("Unexpected Grocy catalog response")
    by_id = {int(p["id"]): {"id": int(p["id"]), "name": str(p.get("name") or ""), "barcodes": []} for p in products}
    for code in codes:
        item = by_id.get(int(code["product_id"]))
        if item and code.get("barcode"):
            item["barcodes"].append(str(code["barcode"]))
    def normalized(name):
        return " ".join("".join(c for c in unicodedata.normalize("NFKD", name.casefold()) if not unicodedata.combining(c)).split())
    groups = {}
    for item in by_id.values():
        name = normalized(item["name"])
        if name:
            groups.setdefault(("Nombre idéntico", name), {})[item["id"]] = item
        for code in item["barcodes"]:
            groups.setdefault(("Mismo código de barras", code), {})[item["id"]] = item
    results = [{"reason": reason, "items": list(items.values())} for (reason, _), items in groups.items() if len(items) > 1]
    seen = {tuple(sorted(item["id"] for item in group["items"])) for group in results}
    entries = list(by_id.values())
    for i, left in enumerate(entries):
        a = normalized(left["name"])
        if len(a) < 6:
            continue
        for right in entries[i+1:]:
            b = normalized(right["name"])
            pair = tuple(sorted((left["id"], right["id"])))
            if pair not in seen and len(b) >= 6 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.88:
                results.append({"reason": "Nombres parecidos · revisar", "items": [left, right]})
                seen.add(pair)
    return results


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
    pending_matches, pending_matches_error = [], False
    if view in ("alexa_matches", "shopping") and (INGRESS_MODE or session.get("auth")):
        try:
            pending_matches = shopping_match_queue.pending(shopping_match_queue.DEFAULT_PATH)
        except Exception:
            pending_matches_error = True
    shopping_match_keys = set()
    if view == "shopping" and pending_matches:
        from shopping_sync import normalize as normalize_alexa_name
        by_key = {match["key"]: match for match in pending_matches}
        for item in shopping:
            key = normalize_alexa_name(item.get("name", ""))
            item["alexa_match"] = by_key.get(key)
            if item["alexa_match"]:
                shopping_match_keys.add(key)
    variants, variants_error = [], False
    if product:
        try:
            variants = variant_catalog.variants_for_product(product["id"])
        except Exception:
            variants_error = True
    if product and (PHOTO_DIR / (str(product["id"]) + ".jpg")).is_file():
        product["image_url"] = url_for("local_product_photo", product_id=product["id"])
    if view == "inventory" and (INGRESS_MODE or session.get("auth")):
        try:
            inventory = barcode_stock.inventory_with_shopping()
        except Exception:
            inventory_error = True
    duplicates, duplicates_error = [], False
    if view == "duplicates" and (INGRESS_MODE or session.get("auth")):
        try:
            duplicates = detect_duplicates()
        except Exception:
            duplicates_error = True
    suggestions = []
    if receipt and view == "ticket":
        try:
            catalog = barcode_stock.list_products()
            for item in receipt["items"]:
                query = str(item.get("name", "")).casefold().strip()
                ranked = sorted(((difflib.SequenceMatcher(None, query, p["name"].casefold()).ratio(), p) for p in catalog), key=lambda x: x[0], reverse=True)
                suggestions.append([p for score, p in ranked[:5] if score >= 0.42 and p["name"].casefold() != query])
        except Exception:
            suggestions = [[] for _ in receipt["items"]]
    return render_template_string(PAGE, csrf=csrf_token(), message=message, suggestions=suggestions, duplicates=duplicates, duplicates_error=duplicates_error,
                                  receipt=receipt, rid=rid, simulation=simulation,
                                  can_commit=can_commit, remove_candidate=remove_candidate, photo=photo,
                                  view=view, inventory=inventory, inventory_error=inventory_error,
                                  shopping=shopping, shopping_error=shopping_error,
                                  shopping_product=shopping_product,
                                  new_product_units=new_product_units,
                                  existing_product=existing_product,
                                  product=product, variants=variants, variants_error=variants_error,
                                  pending_matches=pending_matches, pending_matches_error=pending_matches_error, shopping_match_keys=shopping_match_keys,
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

from api_variants import register_variant_routes
register_variant_routes(app, barcode_stock, variant_catalog, LOCK)


@app.get("/api/v1/inventory")
def api_v1_inventory():
    """Single read-only inventory response; no per-product Grocy requests."""
    try:
        return jsonify({"items": barcode_stock.inventory_with_shopping()})
    except Exception:
        app.logger.exception("api_v1_inventory_failed")
        return jsonify({"error": "inventory_unavailable"}), 503


@app.get("/api/v1/barcodes/<barcode>")
def api_v1_barcode_lookup(barcode):
    """Resolve a scanned code without navigating away from the list."""
    try:
        product = barcode_stock.find_product(barcode)
        if product is None:
            return jsonify({"product_id": None})
        return jsonify({"product_id": int(product["id"])})
    except barcode_stock.BarcodeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("api_v1_barcode_lookup_failed")
        return jsonify({"error": "barcode_lookup_failed"}), 502


@app.post("/api/v1/shopping/products/<int:product_id>/step")
def api_v1_shopping_step(product_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("direction") not in ("plus", "minus"):
        return jsonify({"error": "invalid_direction"}), 400
    if not LOCK.acquire(blocking=False):
        return jsonify({"error": "operation_in_progress"}), 409
    try:
        result = barcode_stock.change_shopping_quantity(product_id, payload["direction"])
    except barcode_stock.BarcodeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("api_v1_shopping_step_failed")
        return jsonify({"error": "shopping_step_failed"}), 502
    finally:
        LOCK.release()
    return jsonify({"product_id": product_id, "amount": result["amount"]})


@app.get("/api/v1/session")
def api_v1_session():
    if not (INGRESS_MODE or session.get("auth")):
        return jsonify({"error": "authentication_required"}), 401
    return jsonify({"csrf_token": csrf_token()})


@app.post("/api/v1/alexa/matches/<key>/choose")
def api_v1_choose_alexa_match(key):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or type(payload.get("product_id")) is not int or payload["product_id"] < 0:
        return jsonify({"error": "invalid_product_id"}), 400
    try:
        if payload["product_id"] == 0:
            shopping_match_queue.keep_original(shopping_match_queue.DEFAULT_PATH, key)
        else:
            shopping_match_queue.choose(shopping_match_queue.DEFAULT_PATH, key, payload["product_id"])
    except (ValueError, TypeError):
        return jsonify({"error": "stale_or_invalid_candidate"}), 409
    except Exception:
        app.logger.exception("api_v1_alexa_choice_failed")
        return jsonify({"error": "selection_failed"}), 502
    return jsonify({"ok": True})


@app.post("/api/v1/shopping/<int:item_id>/toggle")
def api_v1_toggle_shopping(item_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or type(payload.get("done")) is not bool:
        return jsonify({"error": "invalid_done"}), 400
    if not LOCK.acquire(blocking=False):
        return jsonify({"error": "operation_in_progress"}), 409
    try:
        barcode_stock.update_shopping_list_item(item_id, payload["done"])
    except barcode_stock.BarcodeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("api_v1_shopping_toggle_failed")
        return jsonify({"error": "shopping_update_failed"}), 502
    finally:
        LOCK.release()
    return jsonify({"ok": True})


@app.delete("/api/v1/shopping/<int:item_id>")
def api_v1_remove_shopping(item_id):
    if not LOCK.acquire(blocking=False):
        return jsonify({"error": "operation_in_progress"}), 409
    try:
        barcode_stock.remove_shopping_list_item(item_id)
    except barcode_stock.BarcodeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("api_v1_shopping_remove_failed")
        return jsonify({"error": "shopping_remove_failed"}), 502
    finally:
        LOCK.release()
    return jsonify({"ok": True})


@app.get("/api/v1/shopping")
def api_v1_shopping():
    """Read-only shopping snapshot for the v1 frontend; never expose Grocy secrets."""
    if not (INGRESS_MODE or session.get("auth")):
        return jsonify({"error": "authentication_required"}), 401
    try:
        items = barcode_stock.shopping_list_snapshot()
    except Exception:
        app.logger.exception("api_v1_shopping_failed")
        return jsonify({"items": [], "pending_matches": [], "shopping_error": True,
                        "pending_matches_error": False}), 503
    try:
        matches = shopping_match_queue.pending(shopping_match_queue.DEFAULT_PATH)
        matches_error = False
    except Exception:
        app.logger.exception("api_v1_alexa_matches_failed")
        matches, matches_error = [], True
    return jsonify({"items": items, "pending_matches": matches,
                    "shopping_error": False, "pending_matches_error": matches_error})


@app.get("/")
def index():
    if request.args.get("view") == "inventory" and request.args.get("deleted") == "1":
        return render("✅ Artículo eliminado correctamente de Grocy.")
    if request.args.get("view") == "product" and request.args.get("created") == "1":
        return render("✅ Producto creado correctamente en Grocy.")
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

@app.post("/alexa/match/choose")
def alexa_match_choose():
    try:
        shopping_match_queue.choose(
            shopping_match_queue.DEFAULT_PATH,
            request.form.get("key", ""), request.form.get("product_id", ""))
    except (ValueError, TypeError):
        return render("La propuesta ya no es válida. Actualiza y vuelve a elegir."), 409
    except Exception:
        app.logger.exception("alexa_match_choice_failed")
        return render("No se pudo guardar la propuesta; las listas no se han modificado."), 502
    return redirect(url_for("index", view="shopping"))


@app.get("/catalog/audit")
def download_catalog_audit():
    try:
        payload = catalog_audit.build_snapshot()
    except Exception:
        app.logger.exception("catalog_audit_failed")
        return render("No se pudo generar la auditoría. No se ha modificado Grocy."), 502
    response = jsonify(payload)
    response.headers["Content-Disposition"] = 'attachment; filename="despensa-catalog-audit.json"'
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/inventory/barcode-lookup")
def inventory_barcode_lookup():
    try:
        product = barcode_stock.find_product(request.args.get("barcode", ""))
        if not product:
            return jsonify({"error": "Producto no encontrado en tu despensa."}), 404
        return jsonify({"product_id": int(product["id"])})
    except barcode_stock.BarcodeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return jsonify({"error": "No se pudo buscar el código."}), 502


@app.post("/shopping/step/<int:product_id>/<direction>")
def shopping_step(product_id, direction):
    wants_json = request.accept_mimetypes.best_match(
        ["application/json", "text/html"]) == "application/json"
    if not LOCK.acquire(blocking=False):
        if wants_json:
            return jsonify({"error": "Otra operación está en marcha"}), 409
        abort(409, "Otra operación está en marcha")
    try:
        result = barcode_stock.change_shopping_quantity(product_id, direction)
    except barcode_stock.BarcodeError as exc:
        if wants_json:
            return jsonify({"error": str(exc)}), 400
        return render(str(exc)), 400
    except Exception:
        message = "Error de Grocy. Comprueba la lista antes de volver a intentarlo."
        if wants_json:
            return jsonify({"error": message}), 502
        return render(message), 502
    finally:
        LOCK.release()
    if wants_json:
        return jsonify({"amount": result["amount"], "product_id": product_id})
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


@app.post("/shopping/clear-completed")
def shopping_clear_completed():
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        completed_ids = [row["id"] for row in barcode_stock.shopping_list_snapshot() if row["done"]]
        for item_id in completed_ids:
            barcode_stock.remove_shopping_list_item(item_id)
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("No se pudieron eliminar todos los artículos comprados. Actualiza la lista para comprobar cuáles quedan."), 502
    finally:
        LOCK.release()
    return redirect(url_for("index", view="shopping"))


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
            product_id, request.form.get("name"), "1", request.form.get("unit_id"))
    except barcode_stock.BarcodeError as exc:
        return render(str(exc)), 400
    except Exception:
        return render("Error al actualizar el producto. Comprueba Grocy antes de reintentar."), 502
    finally:
        LOCK.release()
    return render("Producto actualizado: " + result["name"] + ". Existencias sin cambios.")


@app.post("/product/<int:product_id>/delete")
def product_delete(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        name = barcode_stock.delete_catalog_product(product_id, request.form.get("expected_name", ""))
    except barcode_stock.BarcodeError as exc:
        return render("❌ No se pudo eliminar: " + str(exc)), 409
    except Exception:
        app.logger.exception("catalog_product_delete_failed")
        return render("❌ La eliminación no se completó. Es posible que el stock se haya descontado; comprueba el artículo en Grocy antes de reintentar."), 502
    finally:
        LOCK.release()
    return redirect(url_for("index", view="inventory", deleted="1"))


@app.post("/product/<int:product_id>/barcode")
def product_barcode_add(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        if (request.form.get("old_barcode") and
                request.form.get("old_barcode") != request.form.get("barcode") and
                variant_catalog.is_registered_variant(request.form["old_barcode"])):
            raise barcode_stock.BarcodeError(
                "Este código pertenece a una variante. No lo sustituyas desde el editor general.")
        if request.form.get("old_barcode"):
            result = barcode_stock.replace_product_barcode(
                product_id, request.form["old_barcode"], request.form.get("barcode", ""))
        else:
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
    return render("Código sin cambios." if result["already_linked"] else
                  ("Código sustituido correctamente sin modificar existencias." if result.get("replaced")
                   else "Código asociado sin modificar existencias."))


@app.post("/product/<int:product_id>/variant")
def product_variant_add(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        result = variant_catalog.save_variant(
            product_id, request.form.get("barcode"), request.form.get("name"),
            supermarket=request.form.get("supermarket"),
            brand=request.form.get("brand"),
            units_per_purchase=request.form.get("units_per_purchase", "1"))
    except (ValueError, barcode_stock.BarcodeError) as exc:
        return render("❌ Variante no guardada: " + str(exc)), 409
    except Exception:
        app.logger.exception("variant_save_failed")
        return render("No se pudo guardar la variante. Comprueba el código en Grocy antes de reintentar."), 502
    finally:
        LOCK.release()
    return redirect(url_for("index", view="product", product_id=result["product_id"]))


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


def cache_remote_product_photo(product_id, url):
    from PIL import Image, ImageOps
    from product_images import safe_image_url
    if not safe_image_url(url):
        raise ValueError("Image host not permitted")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Despensa/0.9"}), timeout=12) as response:
        if response.geturl() != url or response.headers.get("Content-Length") and int(response.headers["Content-Length"]) > 8 * 1024 * 1024:
            raise ValueError("Unexpected image response")
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("Image too large")
    image = Image.open(io.BytesIO(data))
    if image.format not in ("JPEG", "PNG", "WEBP"):
        raise ValueError("Unsupported image format")
    image = ImageOps.exif_transpose(image)
    image.thumbnail((1200, 1200))
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    temp = PHOTO_DIR / (str(product_id) + ".tmp")
    image.convert("RGB").save(temp, format="JPEG", quality=85)
    temp.replace(PHOTO_DIR / (str(product_id) + ".jpg"))


@app.post("/product/<int:product_id>/edit-all")
def product_edit_all(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409)
    try:
        current = barcode_stock.product_detail(product_id)
        name = request.form.get("name", "").strip()
        unit = request.form.get("unit_id")
        amount = request.form.get("desired_amount")
        old_amount = request.form.get("expected_amount")
        new_barcode = request.form.get("barcode", "").strip()
        old_barcode = request.form.get("old_barcode", "").strip()
        photo = request.files.get("photo")
        from decimal import Decimal
        if not name or len(name) > 200 or Decimal(amount) < 0 or Decimal(old_amount) < 0:
            raise ValueError("Datos inválidos")
        if new_barcode:
            barcode_stock.validate_barcode(new_barcode)
        # Detect conflicts before any writes: never partially save an edit.
        if (old_barcode and new_barcode and old_barcode != new_barcode and
                variant_catalog.is_registered_variant(old_barcode)):
            raise ValueError("El código pertenece a una variante. Edítala por separado.")
        if new_barcode and new_barcode != old_barcode:
            owner = barcode_stock.find_product(new_barcode)
            if owner and int(owner["id"]) != int(product_id):
                return redirect(url_for("product_merge_preview", product_id=product_id, barcode=new_barcode))
        barcode_stock.update_product_info(product_id, name, "1", unit)
        if Decimal(amount) != Decimal(old_amount):
            barcode_stock.apply_stock_adjustment(barcode_stock.prepare_stock_adjustment(product_id, amount, old_amount))
        if new_barcode and new_barcode != old_barcode:
            (barcode_stock.replace_product_barcode(product_id, old_barcode, new_barcode) if old_barcode else barcode_stock.associate_product_barcode(product_id, new_barcode))
        if photo and photo.filename:
            from PIL import Image, ImageOps
            data = photo.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("Fotografía demasiado grande")
            image = Image.open(io.BytesIO(data))
            if image.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Formato no admitido")
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1200, 1200))
            PHOTO_DIR.mkdir(parents=True, exist_ok=True)
            temp = PHOTO_DIR / (str(product_id) + ".tmp")
            image.convert("RGB").save(temp, format="JPEG", quality=85)
            temp.replace(PHOTO_DIR / (str(product_id) + ".jpg"))
    except Exception:
        app.logger.exception("Product combined edit failed for %s", product_id)
        return render("No se pudieron guardar todos los cambios. Comprueba la ficha antes de reintentar."), 400
    finally:
        LOCK.release()
    return redirect(url_for("index", view="product", product_id=product_id))


@app.get("/product/<int:product_id>/merge-preview")
def product_merge_preview(product_id):
    if not (INGRESS_MODE or session.get("auth")):
        abort(401)
    try:
        barcode = barcode_stock.validate_barcode(request.args.get("barcode", ""))
        source = barcode_stock.product_detail(product_id)
        owner = barcode_stock.find_product(barcode)
        if not owner or int(owner["id"]) == int(product_id):
            return redirect(url_for("index", view="product", product_id=product_id))
        destination = barcode_stock.product_detail(owner["id"])
    except (ValueError, TypeError, barcode_stock.BarcodeError):
        abort(400)
    return render_template_string("""<!doctype html><html lang="es"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Posible combinación · Despensa</title>
    <style>body{font:16px/1.5 system-ui;background:#f5f7f5;color:#182925;max-width:600px;margin:24px auto;padding:18px}section{background:white;padding:20px;border-radius:16px;margin:16px 0}a{color:#126948}h1{font-size:1.5rem}</style>
    <h1>⚠️ Código ya registrado</h1><p>El código <strong>{{ barcode }}</strong> pertenece a otro artículo. No se ha guardado ningún cambio.</p>
    <section><h2>Artículo que estabas editando</h2><p>{{ source.name }} · ID {{ source.id }}</p><p>Existencias: {{ source.stock_amount }} · unidad {{ source.unit_id }}</p></section>
    <section><h2>Artículo que ya tiene el código</h2><p>{{ destination.name }} · ID {{ destination.id }}</p><p>Existencias: {{ destination.stock_amount }} · unidad {{ destination.unit_id }}</p></section>
    <p>La combinación aún no está habilitada: primero hay que comprobar unidades, existencias y referencias para evitar pérdidas.</p>
    <p><a href="{{ url_for('index', view='product', product_id=source.id) }}">← Volver a editar</a> · <a href="{{ url_for('index', view='product', product_id=destination.id) }}">Ver artículo existente</a></p></html>""", source=source, destination=destination, barcode=barcode)


@app.get("/product/<int:product_id>/photo/local")
def local_product_photo(product_id):
    if not (INGRESS_MODE or session.get("auth")):
        abort(401)
    path = PHOTO_DIR / (str(product_id) + ".jpg")
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="image/jpeg", max_age=3600)


@app.post("/product/<int:product_id>/photo/upload")
def product_photo_upload(product_id):
    if not (INGRESS_MODE or session.get("auth")):
        abort(401)
    uploaded = request.files.get("photo")
    if not uploaded or not uploaded.filename:
        return render("Selecciona una fotografía."), 400
    if not LOCK.acquire(blocking=False):
        abort(409)
    try:
        barcode_stock.product_detail(product_id)
        from PIL import Image, ImageOps
        data = uploaded.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise ValueError("Imagen demasiado grande")
        image = Image.open(io.BytesIO(data))
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError("Formato no admitido")
        image = ImageOps.exif_transpose(image)
        image.thumbnail((1200, 1200))
        image = image.convert("RGB")
        PHOTO_DIR.mkdir(parents=True, exist_ok=True)
        temp = PHOTO_DIR / (str(product_id) + ".tmp")
        image.save(temp, format="JPEG", quality=85)
        temp.replace(PHOTO_DIR / (str(product_id) + ".jpg"))
    except Exception:
        app.logger.exception("Product image upload failed for %s", product_id)
        return render("No se pudo guardar la fotografía. Usa JPG, PNG o WebP (máximo 8 MiB)."), 400
    finally:
        LOCK.release()
    return redirect(url_for("index", view="product", product_id=product_id))


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


@app.post("/product/<int:product_id>/photo/save")
def product_photo_save(product_id):
    if not LOCK.acquire(blocking=False):
        abort(409, "Otra operación está en marcha")
    try:
        product = barcode_stock.product_detail(product_id)
        barcode = barcode_stock.validate_barcode(request.form.get("barcode", ""))
        if barcode not in product["barcodes"]:
            return jsonify({"saved": False}), 400
        # Never trust a client-provided URL: look up the exact associated barcode.
        photo = product_images.lookup_image(barcode)
        if photo:
            barcode_stock.save_product_photo(product_id, photo["image_url"])
            cache_remote_product_photo(product_id, photo["image_url"])
    except Exception:
        return jsonify({"saved": False}), 503
    finally:
        LOCK.release()
    return jsonify({"saved": bool(photo), "image_url": photo["image_url"] if photo else None})


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
    return jsonify({"image_url": found["image_url"] if found else None, "name": found.get("name", "") if found else ""})


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
            image_url=request.form.get("image_url"),
            pack_size=request.form.get("pack_size", "1"))
    except (barcode_stock.BarcodeError, ValueError) as exc:
        return render("❌ No se pudo crear el producto: " + str(exc)), 400
    except Exception:
        app.logger.exception("catalog_product_create_failed: Grocy product creation or lookup failed")
        return render("❌ No se pudo completar el alta en Grocy. Comprueba si el producto existe antes de reintentar. Revisa el registro de Despensa (catalog_product_create_failed)."), 502
    finally:
        LOCK.release()
    if not result["created"]:
        return render("El producto ya existe.", existing_product={
            "id": result["product_id"], "name": result["name"]})
    return redirect(url_for("index", view="product", product_id=result["product_id"], created="1"))


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
    uploads = [f for f in request.files.getlist("ticket") if f and f.filename]
    if len(uploads) != 1:
        abort(400, "Selecciona un archivo o una foto")
    upload = uploads[0]
    if Path(secure_filename(upload.filename or "")).suffix.lower() not in ALLOWED:
        abort(400, "Formato no admitido")
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    rid = secrets.token_hex(16)
    source = DATA / (rid + Path(upload.filename).suffix.lower())
    try:
        upload.save(source)
        receipt = extract.extract(source)
        receipt_path(rid).write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    except Exception:
        app.logger.exception("Receipt upload/extraction failed (request_id=%s)", rid)
        return render("No se pudo procesar el ticket. Comprueba que la imagen sea legible o prueba con un PDF/JPG/PNG diferente. Referencia: " + rid[:8]), 502
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
    session.pop("previewed", None)
    from decimal import Decimal, InvalidOperation
    try:
        for i, item in enumerate(receipt["items"]):
            new_name = request.form.get(f"item_name_{i}", str(item["name"])).strip()
            if not new_name or len(new_name) > 200:
                raise ValueError("Nombre de artículo no válido")
            item["name"] = new_name
            qty = Decimal(request.form.get(f"purchase_units_{i}", str(item["quantity"])))
            factor = Decimal(request.form.get(f"pieces_per_pack_{i}", str(item.get("pieces_per_pack", 1))))
            if (not qty.is_finite() or qty <= 0 or qty != Decimal(str(item["quantity"]))
                    or not factor.is_finite() or factor != factor.to_integral_value()
                    or not 1 <= factor <= 1000):
                raise ValueError("Cantidad o conversión inválida")
            item["purchase_units"] = str(qty)
            item["pieces_per_pack"] = int(factor)
        receipt_path(rid).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    except (ValueError, InvalidOperation, TypeError):
        return render("Revisa los nombres y cantidades: las cantidades deben coincidir con el ticket; las piezas por envase son enteras.", receipt, rid), 400
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
