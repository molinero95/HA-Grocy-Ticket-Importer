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

    @app.post("/api/v1/catalog/products/<int:product_id>/photo")
    def api_v1_upload_catalog_photo(product_id):
        import io
        from pathlib import Path
        from PIL import Image, ImageOps, UnidentifiedImageError
        from flask import current_app
        uploaded = request.files.get("photo")
        if not uploaded or not uploaded.filename:
            return jsonify({"error": "Selecciona una fotografía"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            barcode_stock.product_detail(product_id)
            raw = uploaded.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                return jsonify({"error": "La imagen supera 8 MiB"}), 413
            image = Image.open(io.BytesIO(raw))
            if image.format not in ("JPEG", "PNG", "WEBP"):
                return jsonify({"error": "Formato no admitido. Usa JPG, PNG o WebP"}), 400
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1200, 1200))
            image = image.convert("RGB")
            directory = Path(os.environ.get("PRODUCT_IMAGE_DIR", str(Path(__file__).resolve().parent / "runtime" / "product_images")))
            directory.mkdir(parents=True, exist_ok=True)
            temporary = directory / (str(product_id) + ".tmp")
            image.save(temporary, format="JPEG", quality=85)
            temporary.replace(directory / (str(product_id) + ".jpg"))
        except (UnidentifiedImageError, OSError, ValueError, barcode_stock.BarcodeError):
            current_app.logger.warning("api_v1_catalog_photo_invalid", exc_info=True)
            return jsonify({"error": "Imagen inválida o producto inexistente"}), 400
        except Exception:
            current_app.logger.exception("api_v1_catalog_photo_failed")
            return jsonify({"error": "photo_upload_uncertain"}), 502
        finally:
            lock.release()
        return jsonify({"saved": True, "photo_url": f"product/{product_id}/photo/local"})

    @app.get("/api/v1/catalog/duplicates")
    def api_v1_catalog_duplicates():
        try:
            from duplicate_candidates import detect_duplicates
            return jsonify({"groups": detect_duplicates()})
        except Exception:
            app.logger.exception("api_v1_catalog_duplicates_failed")
            return jsonify({"error": "duplicates_unavailable"}), 503

    @app.get("/api/v1/catalog/products/<int:product_id>/deletion-check")
    def api_v1_check_catalog_deletion(product_id):
        """Read-only deletion eligibility report; never consume stock or delete."""
        payload = {"expected_name": request.args.get("expected_name")}
        if not isinstance(payload, dict) or not isinstance(payload.get("expected_name"), str):
            return jsonify({"error": "expected_name_required"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            from decimal import Decimal
            from variant_catalog import variants_for_product
            from merge_audit import COLLECTIONS, REFERENCES
            product = barcode_stock.grocy("GET", f"objects/products/{product_id}")
            if not isinstance(product, dict) or int(product.get("id", 0)) != product_id:
                return jsonify({"error": "product_not_found"}), 404
            if product.get("name") != payload["expected_name"]:
                return jsonify({"error": "stale_product_name"}), 409
            stock = barcode_stock.grocy("GET", f"stock/products/{product_id}")
            amount = Decimal(str(stock["stock_amount"]))
            if not amount.is_finite() or amount != 0:
                return jsonify({"error": "nonzero_or_invalid_stock"}), 409
            if variants_for_product(product_id):
                return jsonify({"error": "product_has_variants"}), 409
            for collection, _ in COLLECTIONS:
                rows = barcode_stock.grocy("GET", "objects/" + collection)
                if not isinstance(rows, list):
                    return jsonify({"error": "reference_audit_unavailable"}), 409
                if any(isinstance(row, dict) and any(str(row.get(field)) == str(product_id) for field in REFERENCES) for row in rows):
                    return jsonify({"error": "product_has_references", "collection": collection}), 409
            # Historical and external references cannot be audited exhaustively.
            return jsonify({"error": "historical_references_not_audited",
                            "details": "No se elimina el producto hasta verificar historial y referencias externas."}), 409
        except Exception:
            app.logger.exception("api_v1_catalog_delete_audit_failed")
            return jsonify({"error": "product_delete_audit_unavailable"}), 503
        finally:
            lock.release()


    @app.delete("/api/v1/catalog/products/<int:product_id>")
    def api_v1_delete_catalog_product(product_id):
        """Fail-closed deletion: never consume stock or discard linked records."""
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("expected_name"), str):
            return jsonify({"error": "expected_name_required"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            from decimal import Decimal
            from variant_catalog import variants_for_product
            from merge_audit import COLLECTIONS, REFERENCES
            product = barcode_stock.grocy("GET", f"objects/products/{product_id}")
            if not isinstance(product, dict) or int(product.get("id", 0)) != product_id:
                return jsonify({"error": "product_not_found"}), 404
            if product.get("name") != payload["expected_name"]:
                return jsonify({"error": "stale_product_name"}), 409
            stock = barcode_stock.grocy("GET", f"stock/products/{product_id}")
            amount = Decimal(str(stock["stock_amount"]))
            if not amount.is_finite() or amount != 0:
                return jsonify({"error": "nonzero_or_invalid_stock"}), 409
            if variants_for_product(product_id):
                return jsonify({"error": "product_has_variants"}), 409
            for collection, _ in COLLECTIONS:
                rows = barcode_stock.grocy("GET", "objects/" + collection)
                if not isinstance(rows, list):
                    return jsonify({"error": "reference_audit_unavailable"}), 409
                if any(isinstance(row, dict) and any(str(row.get(field)) == str(product_id) for field in REFERENCES) for row in rows):
                    return jsonify({"error": "product_has_references", "collection": collection}), 409
            # Historical and external references cannot be audited exhaustively.
            return jsonify({"error": "historical_references_not_audited",
                            "details": "No se elimina el producto hasta verificar historial y referencias externas."}), 409
        except Exception:
            app.logger.exception("api_v1_catalog_delete_audit_failed")
            return jsonify({"error": "product_delete_audit_unavailable"}), 503
        finally:
            lock.release()


    @app.get("/api/v1/catalog/audit")
    def api_v1_catalog_audit():
        """Read-only export; fail closed on incomplete Grocy data."""
        try:
            from catalog_audit import build_snapshot
            return jsonify(build_snapshot())
        except Exception:
            app.logger.exception("api_v1_catalog_audit_failed")
            return jsonify({"error": "catalog_audit_unavailable"}), 503


    @app.get("/api/v1/catalog/merge-preview")
    def api_v1_catalog_merge_preview():
        try:
            source_id = int(request.args.get("source_id", "0"))
            target_id = int(request.args.get("target_id", "0"))
            if source_id <= 0 or target_id <= 0 or source_id == target_id:
                return jsonify({"error": "Selecciona dos productos distintos"}), 400
            from variant_catalog import variants_for_product
            source = barcode_stock.product_detail(source_id)
            target = barcode_stock.product_detail(target_id)
            source_variants = variants_for_product(source_id)
            target_variants = variants_for_product(target_id)
            blockers = []
            if source["unit_id"] != target["unit_id"]:
                blockers.append("Las unidades de stock son diferentes: no se pueden sumar directamente")
            if source["pack_size"] != target["pack_size"] or source.get("purchase_unit_id") != target.get("purchase_unit_id"):
                blockers.append("Configuración de envases o unidades de compra diferente")
            if source_variants or target_variants:
                blockers.append("Hay variantes de supermercado que requieren migración de referencias")
            if source["stock_amount"] != "0" or target["stock_amount"] != "0":
                blockers.append("Las existencias requieren conciliación y verificación de movimientos")
            from merge_audit import audit_merge
            audit = audit_merge(barcode_stock.grocy, source, target)
            blockers.extend(audit["blockers"])
            if source_variants or target_variants:
                blockers.append("No existe todavía una migración transaccional de variantes")
            return jsonify({"source": source, "target": target,
                            "source_variants": source_variants, "target_variants": target_variants,
                            "audit": audit, "blockers": blockers, "warnings": blockers, "can_merge": False, "merge_allowed": False})
        except (ValueError, TypeError, barcode_stock.BarcodeError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("api_v1_catalog_merge_preview_failed")
            return jsonify({"error": "merge_preview_unavailable"}), 503
