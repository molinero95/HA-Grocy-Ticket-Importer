"""Versioned JSON endpoints for generic products and supermarket variants.

The domain service audits Grocy barcode ownership; this module never moves stock.
Routes are registered on the existing Flask app to preserve endpoint names.
"""
from flask import jsonify, request


def register_variant_routes(app, barcode_stock, variant_catalog, lock):
    @app.post("/api/v1/products/<int:product_id>/variants")
    def api_v1_save_variant(product_id):
        """Add or update variant metadata; never move stock between products."""
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        barcode = payload.get("barcode")
        name = payload.get("name")
        supermarket = payload.get("supermarket", "")
        brand = payload.get("brand", "")
        units = payload.get("units_per_purchase", "1")
        if not all(isinstance(value, str) for value in (barcode, name, supermarket, brand)) or not isinstance(units, (str, int, float)) or isinstance(units, bool):
            return jsonify({"error": "invalid_variant"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            result = variant_catalog.save_variant(product_id, barcode, name,
                supermarket=supermarket, brand=brand, units_per_purchase=units)
        except (ValueError, barcode_stock.BarcodeError) as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_variant_save_failed")
            return jsonify({"error": "variant_save_failed_check_grocy_before_retry"}), 502
        finally:
            lock.release()
        return jsonify({"ok": True, "result": result})


    @app.get("/api/v1/products/<int:product_id>/variants")
    def api_v1_product_variants(product_id):
        """Read variant metadata without changing Grocy's canonical stock."""
        try:
            products = barcode_stock.list_products()
            product = next((p for p in products if p["id"] == product_id), None)
            if product is None:
                return jsonify({"error": "product_not_found"}), 404
            return jsonify({"product": product, "variants": variant_catalog.variants_for_product(product_id)})
        except Exception:
            app.logger.exception("api_v1_variants_failed")
            return jsonify({"error": "variants_unavailable"}), 503


