"""Shopping list, Alexa decisions and session endpoints for v1."""
import hmac
import os
from flask import jsonify, request, session
from stock_commands import CommandConflict


def register_shopping_routes(app, barcode_stock, shopping_match_queue, lock, ingress_mode, csrf_token):
    @app.get("/api/v1/auth/status")
    def api_v1_auth_status():
        return jsonify({"authenticated": bool(ingress_mode() or session.get("auth")),
                        "ingress": bool(ingress_mode()), "csrf_token": csrf_token()})

    @app.post("/api/v1/auth/login")
    def api_v1_auth_login():
        if ingress_mode():
            return jsonify({"authenticated": True})
        payload = request.get_json(silent=True)
        password = payload.get("password") if isinstance(payload, dict) else None
        expected = os.environ.get("WEB_PASSWORD")
        if not isinstance(password, str) or not expected or not hmac.compare_digest(password.encode("utf-8"), expected.encode("utf-8")):
            return jsonify({"error": "invalid_credentials"}), 401
        session.clear()
        session["auth"] = True
        return jsonify({"authenticated": True, "csrf_token": csrf_token()})

    @app.post("/api/v1/auth/logout")
    def api_v1_auth_logout():
        if ingress_mode():
            return jsonify({"error": "ingress_managed_authentication"}), 409
        session.clear()
        return jsonify({"authenticated": False})


    @app.get("/api/v1/session")
    def api_v1_session():
        if not (ingress_mode() or session.get("auth")):
            return jsonify({"error": "authentication_required"}), 401
        return jsonify({"csrf_token": csrf_token()})


    @app.post("/api/v1/alexa/matches/<key>/choose")
    def api_v1_choose_alexa_match(key):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or type(payload.get("product_id")) is not int or payload["product_id"] < 0:
            return jsonify({"error": "invalid_product_id"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            from shopping_choice_conversion import manual_choice
            with shopping_match_queue.mutation_lock(shopping_match_queue.DEFAULT_PATH, blocking=False):
                result = manual_choice(barcode_stock.grocy, shopping_match_queue,
                    shopping_match_queue.DEFAULT_PATH, key, payload["product_id"], payload.get("operation_id"))
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except CommandConflict:
            return jsonify({"error": "selection_uncertain", "details": "Actualiza la lista y comprueba Grocy antes de guardar otra vez. La elección no se ha reenviado."}), 409
        except (ValueError, TypeError) as exc:
            return jsonify({"error": "stale_or_invalid_candidate", "details": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_alexa_choice_failed")
            return jsonify({"error": "selection_failed", "details": "No se pudo confirmar la elección. Actualiza la lista antes de reintentar."}), 502
        finally:
            lock.release()
        return jsonify(result)


    @app.delete("/api/v1/alexa/matches/<key>")
    def api_v1_remove_alexa_match(key):
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            from shopping_choice_conversion import remove_pending
            with shopping_match_queue.mutation_lock(shopping_match_queue.DEFAULT_PATH, blocking=False):
                result = remove_pending(barcode_stock.grocy, shopping_match_queue,
                                        shopping_match_queue.DEFAULT_PATH, key)
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except (ValueError, TypeError) as exc:
            return jsonify({"error": "shopping_remove_failed", "details": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_pending_remove_failed")
            return jsonify({"error": "shopping_remove_failed"}), 502
        finally:
            lock.release()
        return jsonify(result)


    @app.post("/api/v1/shopping/<int:item_id>/toggle")
    def api_v1_toggle_shopping(item_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or type(payload.get("done")) is not bool:
            return jsonify({"error": "invalid_done"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            with shopping_match_queue.mutation_lock(shopping_match_queue.DEFAULT_PATH, blocking=False):
                barcode_stock.update_shopping_list_item(item_id, payload["done"])
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
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
            with shopping_match_queue.mutation_lock(shopping_match_queue.DEFAULT_PATH, blocking=False):
                pending = shopping_match_queue.pending(shopping_match_queue.DEFAULT_PATH)
                if pending:
                    from shopping_choice_conversion import delete_verified
                    original = barcode_stock.grocy("GET", f"objects/shopping_list/{item_id}")
                    if (not isinstance(original, dict) or int(original.get("id") or 0) != item_id
                            or int(original.get("shopping_list_id") or 1) != 1):
                        raise barcode_stock.BarcodeError("El artículo pertenece a otra lista")
                    shopping_match_queue.stage_entry_removal(shopping_match_queue.DEFAULT_PATH, original)
                    delete_verified(barcode_stock.grocy, original)
                else:
                    barcode_stock.remove_shopping_list_item(item_id)
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except (ValueError, TypeError, barcode_stock.BarcodeError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("api_v1_shopping_remove_failed")
            return jsonify({"error": "shopping_remove_failed"}), 502
        finally:
            lock.release()
        return jsonify({"ok": True})


    @app.post("/api/v1/shopping/clear-completed")
    def api_v1_clear_completed_shopping():
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        removed = 0
        try:
            with shopping_match_queue.mutation_lock(shopping_match_queue.DEFAULT_PATH, blocking=False):
                completed = [row["id"] for row in barcode_stock.shopping_list_snapshot() if row["done"]]
                for item_id in completed:
                    barcode_stock.remove_shopping_list_item(item_id, expected_done=True)
                    removed += 1
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except Exception:
            app.logger.exception("api_v1_shopping_clear_completed_failed")
            return jsonify({"error": "partial_clear_uncertain", "removed": removed,
                            "details": "Actualiza la lista antes de reintentar."}), 502
        finally:
            lock.release()
        return jsonify({"removed": removed})


    @app.get("/api/v1/shopping")
    def api_v1_shopping():
        """Read-only shopping snapshot for the v1 frontend; never expose Grocy secrets."""
        if not (ingress_mode() or session.get("auth")):
            return jsonify({"error": "authentication_required"}), 401
        try:
            items = barcode_stock.shopping_list_snapshot()
            from api_photos import local_image_url
            for item in items:
                if item.get("product_id"):
                    item["image_url"] = local_image_url(item["product_id"]) or item.get("image_url")
        except Exception:
            app.logger.exception("api_v1_shopping_failed")
            return jsonify({"items": [], "pending_matches": [], "shopping_error": True,
                            "pending_matches_error": False}), 503
        try:
            matches = [row for row in shopping_match_queue.pending(shopping_match_queue.DEFAULT_PATH)
                       if not row.get("removed") and (not row.get("dismissed") or row.get("selection_stale"))]
            matches_error = False
        except Exception:
            app.logger.exception("api_v1_alexa_matches_failed")
            matches, matches_error = [], True
        from shopping_sync_status import snapshot
        return jsonify({"items": items, "pending_matches": matches,
                        "sync": snapshot(shopping_match_queue.DEFAULT_PATH),
                        "shopping_error": False, "pending_matches_error": matches_error})


