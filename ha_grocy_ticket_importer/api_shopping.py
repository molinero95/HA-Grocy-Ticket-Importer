"""Shopping list, Alexa decisions and session endpoints for v1."""
from flask import jsonify, request, session


def register_shopping_routes(app, barcode_stock, shopping_match_queue, lock, ingress_mode, csrf_token):
    @app.get("/api/v1/session")
    def api_v1_session():
        if not (ingress_mode or session.get("auth")):
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
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            barcode_stock.update_shopping_list_item(item_id, payload["done"])
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("api_v1_shopping_toggle_failed")
            return jsonify({"error": "shopping_update_failed"}), 502
        finally:
            lock.release()
        return jsonify({"ok": True})


    @app.delete("/api/v1/shopping/<int:item_id>")
    def api_v1_remove_shopping(item_id):
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            barcode_stock.remove_shopping_list_item(item_id)
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("api_v1_shopping_remove_failed")
            return jsonify({"error": "shopping_remove_failed"}), 502
        finally:
            lock.release()
        return jsonify({"ok": True})


    @app.get("/api/v1/shopping")
    def api_v1_shopping():
        """Read-only shopping snapshot for the v1 frontend; never expose Grocy secrets."""
        if not (ingress_mode or session.get("auth")):
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


