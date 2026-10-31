"""Inventory, barcode lookup and shopping quantity endpoints for the v1 API."""
from flask import jsonify, request


def register_inventory_routes(app, barcode_stock, lock):
    @app.get("/api/v1/inventory")
    def api_v1_inventory():
        """Single read-only inventory response; no per-product Grocy requests."""
        try:
            items = barcode_stock.inventory_with_shopping()
            from pathlib import Path
            import os
            directory = Path(os.environ.get("PRODUCT_IMAGE_DIR", str(Path(__file__).resolve().parent / "runtime" / "product_images")))
            for item in items:
                if (directory / (str(item["id"]) + ".jpg")).is_file():
                    item["image_url"] = f"product/{item['id']}/photo/local"
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
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or payload.get("direction") not in ("plus", "minus"):
            return jsonify({"error": "invalid_direction"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            result = barcode_stock.change_shopping_quantity(product_id, payload["direction"])
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("api_v1_shopping_step_failed")
            return jsonify({"error": "shopping_step_failed"}), 502
        finally:
            lock.release()
        return jsonify({"product_id": product_id, "amount": result["amount"]})


