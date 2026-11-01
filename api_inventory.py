"""Inventory, barcode lookup and shopping quantity endpoints for the v1 API."""
from flask import jsonify, request


def register_inventory_routes(app, barcode_stock, lock):
    @app.get("/api/v1/shopping/products/<int:product_id>/options")
    def api_v1_shopping_options(product_id):
        try:
            return jsonify(barcode_stock.shopping_product_options(product_id))
        except (barcode_stock.BarcodeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            return jsonify({"error": "No se pudieron consultar las unidades de compra"}), 503

    @app.post("/api/v1/shopping/products/<int:product_id>/add")
    def api_v1_shopping_add_amount(product_id):
        from stock_commands import execute_once, CommandConflict
        from shopping_match_queue import mutation_lock, DEFAULT_PATH
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            def add():
                try:
                    name = barcode_stock.add_to_shopping_list(product_id, payload.get("amount"), payload.get("unit_id"))
                    return {"status": 200, "body": {"name": name}}
                except (barcode_stock.BarcodeError, ValueError) as exc:
                    return {"status": 409, "body": {"error": str(exc)}}
            with mutation_lock(DEFAULT_PATH, blocking=False):
                result = execute_once(payload.get("operation_id"), {**payload, "product_id": product_id, "command": "shopping_add"}, add)
            return jsonify(result["body"]), result["status"]
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except CommandConflict as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            return jsonify({"error": "Comprueba la lista antes de añadir otra vez este producto"}), 502
        finally:
            lock.release()

    @app.get("/api/v1/inventory")
    def api_v1_inventory():
        """Single read-only inventory response; no per-product Grocy requests."""
        try:
            items = barcode_stock.inventory_with_shopping()
            from api_photos import local_image_url
            from stock_thresholds import settings
            limits = settings()
            for item in items:
                warning = limits.get(item['id'], {'amount': '0', 'warning_enabled': True})
                item['stock_threshold'] = warning['amount']
                item['stock_warning_enabled'] = warning['warning_enabled']
                item["image_url"] = local_image_url(item["id"]) or item.get("image_url")
            return jsonify({"items": items})
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
        from shopping_match_queue import mutation_lock, DEFAULT_PATH
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or payload.get("direction") not in ("plus", "minus"):
            return jsonify({"error": "invalid_direction"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            with mutation_lock(DEFAULT_PATH, blocking=False):
                result = barcode_stock.change_shopping_quantity(product_id, payload["direction"])
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("api_v1_shopping_step_failed")
            return jsonify({"error": "shopping_step_failed"}), 502
        finally:
            lock.release()
        return jsonify({"product_id": product_id, "amount": result["amount"]})


