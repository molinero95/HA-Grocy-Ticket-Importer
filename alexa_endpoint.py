"""Dedicated read-only Alexa listener. Never mounts the ingress application."""

import os
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from flask import Flask, jsonify, request
from alexa_verification import verify, InvalidAlexaRequest
import barcode_stock
import importer
import shopping_match_queue
import variant_catalog
from shopping_sync import normalize

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 65536


def local_metadata():
    aliases, limits = [], {}
    paths = ((shopping_match_queue.DEFAULT_PATH, "aliases"), (variant_catalog.CATALOG_DB, "limits"))
    for path, kind in paths:
        path = Path(path)
        if not path.is_file():
            continue
        with closing(
            sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
        ) as db:
            table = "alexa_aliases" if kind == "aliases" else "stock_thresholds"
            if not db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone():
                continue
            if kind == "aliases":
                aliases = [
                    {"name": name, "product_id": pid}
                    for name, pid in db.execute("SELECT display_name,product_id FROM alexa_aliases")
                ]
            else:
                columns = {row[1] for row in db.execute("PRAGMA table_info(stock_thresholds)")}
                enabled = "warning_enabled" if "warning_enabled" in columns else "1"
                limits = {
                    pid: (Decimal(amount), bool(warning))
                    for pid, amount, warning in db.execute(
                        "SELECT product_id,amount," + enabled + " FROM stock_thresholds"
                    )
                }
    return aliases, limits


def speak(text, reprompt=None):
    response = {
        "outputSpeech": {"type": "PlainText", "text": text},
        "shouldEndSession": reprompt is None,
    }
    if reprompt:
        response["reprompt"] = {"outputSpeech": {"type": "PlainText", "text": reprompt}}
    return {"version": "1.0", "response": response}


def quantity(row):
    amount = Decimal(row["amount"])
    if not amount.is_finite():
        raise ValueError("Stock unavailable")
    value = format(amount.normalize(), "f").replace(".", ",")
    unit = normalize(row["unit"])
    unit = (
        "kilos"
        if unit in ("kg", "kilogram", "kilograms", "kilogramo", "kilogramos")
        else "unidades" if unit in ("piece", "pieces", "unidad", "unidades") else row["unit"][:50]
    )
    return f"{row['name'][:200]}: {value} {unit}"


def answer(payload):
    req = payload["request"]
    kind = req.get("type")
    if kind == "SessionEndedRequest":
        return {"version": "1.0", "response": {}}
    intent = req.get("intent", {})
    name = intent.get("name")
    if name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
        return speak("Hasta luego.")
    help_text = "Puedes preguntar cuánto queda de leche, si tenemos arroz o qué productos tienen stock bajo."
    if kind == "LaunchRequest" or name in ("AMAZON.HelpIntent", "AMAZON.FallbackIntent"):
        return speak(help_text, "¿Qué producto quieres consultar?")
    if kind != "IntentRequest" or name not in ("GetStockIntent", "LowStockIntent"):
        return speak(help_text, "¿Qué producto quieres consultar?")
    term = intent.get("slots", {}).get("Product", {}).get("value", "")
    if name == "GetStockIntent" and (not isinstance(term, str) or not 0 < len(term.strip()) <= 200):
        return speak(
            "Dime el nombre del producto.", "¿De qué producto quieres saber las existencias?"
        )
    rows = barcode_stock.inventory_snapshot(
        read=lambda method, path: importer.grocy(method, path, timeout=1)
    )
    aliases, limits = local_metadata()
    if name == "LowStockIntent":
        low = []
        for row in rows:
            threshold, enabled = limits.get(row["id"], (Decimal("0"), True))
            if not threshold.is_finite():
                raise ValueError("Threshold unavailable")
            if enabled and Decimal(row["amount"]) <= threshold:
                low.append(row)
        if not low:
            return speak("No hay productos con avisos de stock bajo.")
        message = "; ".join(quantity(row) for row in low[:5])
        return speak(
            f'Hay {len(low)} {"producto" if len(low) == 1 else "productos"} con stock bajo. {message}.'
            + (" Hay más en Despensa." if len(low) > 5 else "")
        )
    key = normalize(term)
    exact_ids = {row["product_id"] for row in aliases if normalize(row["name"]) == key}
    exact = [row for row in rows if normalize(row["name"]) == key or row["id"] in exact_ids]
    matches = exact or [
        row for row in rows if key and set(key.split()).issubset(normalize(row["name"]).split())
    ]
    if not matches:
        return speak("No encuentro ese producto en tu catálogo. Comprueba el nombre en Despensa.")
    if len(matches) > 1:
        options = ", ".join(row["name"][:100] for row in matches[:4])
        return speak(
            "He encontrado varios productos: " + options + ". Pregunta por su nombre completo.",
            "¿Cuánto queda de qué producto?",
        )
    return speak(quantity(matches[0]) + ".")


@app.after_request
def private_response(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.post("/alexa/despensa")
def alexa_stock():
    skill_id, user_id = os.environ.get("ALEXA_SKILL_ID", ""), os.environ.get(
        "ALEXA_SKILL_USER_ID", ""
    )
    if os.environ.get("ALEXA_SKILL_ENABLED") != "1" or not skill_id or not user_id:
        return jsonify({"error": "alexa_skill_disabled"}), 503
    try:
        payload = verify(request.get_data(), request.headers, skill_id, user_id)
    except InvalidAlexaRequest:
        return jsonify({"error": "invalid_alexa_request"}), 400
    if payload["request"].get("locale", "es-ES") != "es-ES":
        return jsonify(speak("Esta skill está configurada en español de España."))
    try:
        return jsonify(answer(payload))
    except Exception:
        # Never log request bodies, private product names or credentials.
        return jsonify(speak("No puedo consultar las existencias ahora. Inténtalo más tarde."))
