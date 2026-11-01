"""Alexa alias API routes."""
from flask import jsonify, request
from shopping_aliases import list_aliases, set_alias, remove_alias
from shopping_match_queue import DEFAULT_PATH, mutation_lock
from importer import grocy


def register_alias_routes(app):
    @app.get("/api/v1/alexa/aliases")
    def api_v1_alexa_aliases():
        return jsonify({"aliases": list_aliases(DEFAULT_PATH)})

    @app.post("/api/v1/alexa/aliases")
    def api_v1_save_alexa_alias():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        pid = payload.get("product_id")
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or type(pid) is not int or pid <= 0:
            return jsonify({"error": "invalid_payload"}), 400
        with mutation_lock(DEFAULT_PATH):
            products = grocy("GET", "objects/products")
            if not isinstance(products, list):
                return jsonify({"error": "catalog_unavailable"}), 503
            if not any(int(p["id"]) == pid for p in products):
                return jsonify({"error": "product_not_found"}), 404
            try:
                set_alias(DEFAULT_PATH, name, pid)
            except ValueError:
                return jsonify({"error": "alias_conflict"}), 409
        return jsonify({"ok": True}), 201

    @app.delete("/api/v1/alexa/aliases/<path:key>")
    def api_v1_delete_alexa_alias(key):
        with mutation_lock(DEFAULT_PATH):
            remove_alias(DEFAULT_PATH, key)
        return jsonify({"ok": True})
