"""Product catalog API with safe reuse of existing Grocy domain operations."""
import os
from flask import jsonify, request


def register_catalog_routes(app, barcode_stock, lock):
    @app.get("/api/v1/catalog/units")
    def api_v1_catalog_units():
        try:
            return jsonify({"units": barcode_stock.new_product_units()})
        except Exception:
            app.logger.exception("api_v1_catalog_units_failed")
            return jsonify({"error": "catalog_units_unavailable"}), 503

    @app.post("/api/v1/catalog/products")
    def api_v1_create_catalog_product():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            result = barcode_stock.create_catalog_product(
                payload.get("name"), payload.get("barcode", ""), payload.get("unit_id"),
                payload.get("initial_stock", "0"), location_id=int(os.getenv("GROCY_LOCATION_ID", "2")),
                pack_size=payload.get("pack_size", "1"))
        except (barcode_stock.BarcodeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("api_v1_catalog_create_failed")
            return jsonify({"error": "catalog_create_uncertain", "details": "Comprueba Grocy antes de reintentar."}), 502
        finally:
            lock.release()
        return jsonify(result), 201 if result["created"] else 200

    @app.patch("/api/v1/catalog/products/<int:product_id>")
    def api_v1_edit_catalog_product(product_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            result = barcode_stock.update_product_info(product_id, payload.get("name"), "1", payload.get("unit_id"))
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("api_v1_catalog_edit_failed")
            return jsonify({"error": "catalog_edit_uncertain"}), 502
        finally:
            lock.release()
        return jsonify(result)

    @app.post("/api/v1/catalog/products/<int:product_id>/stock")
    def api_v1_adjust_catalog_stock(product_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or "desired_amount" not in payload or "expected_amount" not in payload:
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            preview = barcode_stock.prepare_stock_adjustment(product_id, payload["desired_amount"], payload["expected_amount"])
            result = barcode_stock.apply_stock_adjustment(preview)
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_catalog_stock_uncertain")
            return jsonify({"error": "stock_update_uncertain", "details": "Comprueba el stock de Grocy antes de reintentar."}), 502
        finally:
            lock.release()
        return jsonify(result)

    @app.get("/api/v1/catalog/products/<int:product_id>/barcodes")
    def api_v1_catalog_barcodes(product_id):
        try:
            rows = barcode_stock.grocy("GET", "objects/product_barcodes")
            if not isinstance(rows, list):
                raise ValueError("Invalid barcode response")
            return jsonify({"barcodes": sorted({str(row["barcode"]) for row in rows if int(row["product_id"]) == product_id})})
        except Exception:
            app.logger.exception("api_v1_catalog_barcodes_failed")
            return jsonify({"error": "barcodes_unavailable"}), 503

    @app.post("/api/v1/catalog/products/<int:product_id>/barcodes")
    def api_v1_add_catalog_barcode(product_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            result = barcode_stock.associate_product_barcode(product_id, payload.get("barcode"))
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_catalog_barcode_add_failed")
            return jsonify({"error": "barcode_add_uncertain"}), 502
        finally:
            lock.release()
        return jsonify(result)

    @app.patch("/api/v1/catalog/products/<int:product_id>/barcodes/<old_barcode>")
    def api_v1_replace_catalog_barcode(product_id, old_barcode):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            from variant_catalog import is_registered_variant
            if is_registered_variant(old_barcode):
                return jsonify({"error": "Este código pertenece a una variante. Edítalo desde la variante."}), 409
            result = barcode_stock.replace_product_barcode(product_id, old_barcode, payload.get("barcode"))
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_catalog_barcode_replace_failed")
            return jsonify({"error": "barcode_replace_uncertain"}), 502
        finally:
            lock.release()
        return jsonify(result)

    @app.delete("/api/v1/catalog/products/<int:product_id>/barcodes/<barcode>")
    def api_v1_remove_catalog_barcode(product_id, barcode):
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            result = barcode_stock.remove_product_barcode(product_id, barcode)
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_catalog_barcode_remove_failed")
            return jsonify({"error": "barcode_remove_uncertain", "details": "Comprueba los códigos de Grocy antes de reintentar."}), 502
        finally:
            lock.release()
        return jsonify(result)
