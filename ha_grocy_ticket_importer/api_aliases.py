"""Alexa alias API routes."""
from flask import jsonify, request
from shopping_aliases import list_aliases, set_alias, remove_alias, update_alias
from shopping_match_queue import DEFAULT_PATH, mutation_lock
from importer import grocy


def register_alias_routes(app):
    @app.get("/api/v1/alexa/aliases")
    def api_v1_alexa_aliases():
        try:
            aliases = list_aliases(DEFAULT_PATH)
            try:
                from shopping_match_queue import pending
                suggestions = sorted({row['name'] for row in pending(DEFAULT_PATH)
                                      if not row.get('removed') and isinstance(row.get('name'), str)
                                      and 0 < len(row['name']) <= 200})
            except Exception:
                suggestions = []
            return jsonify({"aliases": aliases, "suggestions": suggestions})
        except Exception:
            return jsonify({"error": "aliases_unavailable"}), 503

    @app.post("/api/v1/alexa/aliases")
    def api_v1_save_alexa_alias():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        name = payload.get("name")
        pid = payload.get("product_id")
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or type(pid) is not int or pid <= 0:
            return jsonify({"error": "invalid_payload"}), 400
        try:
            with mutation_lock(DEFAULT_PATH, blocking=False):
                products = grocy("GET", "objects/products")
                if not isinstance(products, list):
                    return jsonify({"error": "catalog_unavailable"}), 503
                from shopping_sync_adapters import _grocy_done
                if not any(int(p["id"]) == pid and _grocy_done(p.get("active", True)) for p in products):
                    return jsonify({"error": "product_not_found"}), 404
                set_alias(DEFAULT_PATH, name, pid)
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except ValueError:
            return jsonify({"error": "alias_conflict"}), 409
        except Exception:
            return jsonify({"error": "aliases_unavailable"}), 503
        return jsonify({"ok": True}), 201

    @app.put("/api/v1/alexa/aliases/<path:key>")
    def api_v1_update_alexa_alias(key):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        name, pid = payload.get("name"), payload.get("product_id")
        expected_name, expected_pid = payload.get("expected_name"), payload.get("expected_product_id")
        if (not isinstance(name, str) or not name.strip() or len(name) > 200
                or type(pid) is not int or pid <= 0
                or not isinstance(expected_name, str) or not expected_name.strip() or len(expected_name) > 200
                or type(expected_pid) is not int or expected_pid <= 0):
            return jsonify({"error": "invalid_payload"}), 400
        try:
            with mutation_lock(DEFAULT_PATH, blocking=False):
                products = grocy("GET", "objects/products")
                if not isinstance(products, list):
                    return jsonify({"error": "catalog_unavailable"}), 503
                from shopping_sync_adapters import _grocy_done
                if not any(int(p["id"]) == pid and _grocy_done(p.get("active", True)) for p in products):
                    return jsonify({"error": "product_not_found"}), 404
                alias = update_alias(DEFAULT_PATH, key, expected_name=expected_name,
                                     expected_product_id=expected_pid, name=name, product_id=pid)
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except ValueError:
            return jsonify({"error": "alias_conflict"}), 409
        except Exception:
            return jsonify({"error": "aliases_unavailable"}), 503
        return jsonify({"alias": alias})

    @app.delete("/api/v1/alexa/aliases/<path:key>")
    def api_v1_delete_alexa_alias(key):
        payload = request.get_json(silent=True) or {}
        pid = payload.get("product_id") if isinstance(payload, dict) else None
        if type(pid) is not int or pid <= 0:
            return jsonify({"error": "invalid_payload"}), 400
        try:
            with mutation_lock(DEFAULT_PATH, blocking=False):
                remove_alias(DEFAULT_PATH, key, pid)
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except ValueError:
            return jsonify({"error": "alias_conflict"}), 409
        except Exception:
            return jsonify({"error": "aliases_unavailable"}), 503
        return jsonify({"ok": True})
