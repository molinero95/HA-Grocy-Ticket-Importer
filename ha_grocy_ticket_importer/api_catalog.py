"""Product catalog API with safe reuse of existing Grocy domain operations."""
import os
from flask import jsonify, request


def register_catalog_routes(app, barcode_stock, lock):
    @app.get("/api/v1/catalog/archived")
    def api_v1_archived_products():
        from catalog_lifecycle import archived_inventory
        try:
            return jsonify({"items": archived_inventory()})
        except Exception:
            app.logger.exception("api_v1_archived_unavailable")
            return jsonify({"error": "No se pudieron cargar los productos archivados"}), 503

    @app.post("/api/v1/catalog/products/<int:product_id>/active")
    def api_v1_set_product_active(product_id):
        from catalog_lifecycle import set_active
        from stock_commands import execute_once, CommandConflict
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or type(payload.get("active")) is not bool or not isinstance(payload.get("expected_name"), str):
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            def change():
                try:
                    return {"status": 200, "body": set_active(product_id, payload["expected_name"], payload["active"])}
                except barcode_stock.BarcodeError as exc:
                    return {"status": 409, "body": {"error": str(exc)}}
            result = execute_once(payload.get("operation_id"), {**payload, "product_id": product_id, "command": "active"}, change)
            return jsonify(result["body"]), result["status"]
        except CommandConflict as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_product_active_uncertain")
            return jsonify({"error": "Actualiza el catálogo para comprobar el estado del producto antes de reintentar"}), 502
        finally:
            lock.release()

    @app.post("/api/v1/catalog/products/<int:product_id>/purchase")
    def api_v1_purchase_configuration(product_id):
        from purchase_units import update_purchase_configuration
        from stock_commands import execute_once, CommandConflict
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("expected"), dict):
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            def change():
                try:
                    body = update_purchase_configuration(barcode_stock.grocy, product_id, payload.get("purchase_unit_id"), payload.get("factor"), payload["expected"])
                    return {"status": 200, "body": body}
                except (ValueError, TypeError, ArithmeticError) as exc:
                    return {"status": 409, "body": {"error": str(exc)}}
            result = execute_once(payload.get("operation_id"), {**payload, "product_id": product_id, "command": "purchase"}, change)
            return jsonify(result["body"]), result["status"]
        except CommandConflict as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_purchase_uncertain")
            return jsonify({"error": "Actualiza la ficha y comprueba la configuración en Grocy antes de reintentar"}), 502
        finally:
            lock.release()

    @app.get("/api/v1/catalog/units")
    def api_v1_catalog_units():
        try:
            return jsonify({"units": barcode_stock.new_product_units()})
        except Exception:
            app.logger.exception("api_v1_catalog_units_failed")
            return jsonify({"error": "catalog_units_unavailable"}), 503

    @app.get("/api/v1/catalog/products/<int:product_id>")
    def api_v1_catalog_product(product_id):
        try:
            from api_photos import local_image_url
            product = barcode_stock.product_detail(product_id)
            product["image_url"] = local_image_url(product_id) or product.get("image_url")
            from stock_thresholds import settings
            warning = settings().get(product_id, {"amount": "0", "warning_enabled": True})
            product["stock_threshold"] = warning["amount"]
            product["stock_warning_enabled"] = warning["warning_enabled"]
            return jsonify(product)
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception:
            app.logger.exception("api_v1_catalog_product_unavailable")
            return jsonify({"error": "No se pudo cargar el producto"}), 503

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
            result = barcode_stock.update_product_info(product_id, payload.get("name"), None, payload.get("unit_id"))
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("api_v1_catalog_edit_failed")
            return jsonify({"error": "catalog_edit_uncertain"}), 502
        finally:
            lock.release()
        return jsonify(result)

    @app.put('/api/v1/catalog/products/<int:product_id>/stock-threshold')
    def api_v1_stock_threshold(product_id):
        from stock_thresholds import save_threshold
        payload = request.get_json(silent=True)
        if (not isinstance(payload, dict) or any(not isinstance(payload.get(key), str) for key in ('amount', 'expected'))
                or any(type(payload.get(key, True)) is not bool for key in ('warning_enabled', 'expected_warning_enabled'))):
            return jsonify({"error": "Indica un umbral válido y actualiza la ficha."}), 400
        if not lock.acquire(blocking=False): return jsonify({"error": "operation_in_progress"}), 409
        try:
            product = barcode_stock.grocy('GET', f'objects/products/{product_id}')
            if not isinstance(product, dict) or int(product.get('id', 0)) != product_id:
                return jsonify({"error": "El producto ya no está disponible."}), 409
            return jsonify({"stock_threshold": save_threshold(product_id, payload['amount'], payload['expected'], payload.get('warning_enabled', True), payload.get('expected_warning_enabled', True)), 'stock_warning_enabled': payload.get('warning_enabled', True)})
        except ValueError as exc: return jsonify({"error": str(exc)}), 409
        except Exception: return jsonify({"error": "No se pudo guardar el umbral. Vuelve a consultar la ficha."}), 503
        finally: lock.release()

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

    @app.post("/api/v1/catalog/products/<int:product_id>/consume")
    def api_v1_consume_catalog_product(product_id):
        from stock_commands import execute_once, CommandConflict
        payload = request.get_json(silent=True)
        if (not isinstance(payload, dict) or type(payload.get("add_to_list")) is not bool
                or not isinstance(payload.get("expected_amount"), str)
                or not isinstance(payload.get("amount"), str)):
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            def consume():
                try:
                    result = barcode_stock.consume_product_quantity(product_id, payload["amount"], payload["expected_amount"], payload["add_to_list"])
                    return {"status": 200, "body": result}
                except barcode_stock.BarcodeError as exc:
                    return {"status": 409, "body": {"error": str(exc)}}
            result = execute_once(payload.get("operation_id"), {**payload, "product_id": product_id}, consume)
            return jsonify(result["body"]), result["status"]
        except CommandConflict as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            app.logger.exception("api_v1_consume_uncertain")
            return jsonify({"error": "Resultado incierto. Comprueba Grocy antes de volver a consumir."}), 502
        finally:
            lock.release()

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

    @app.get("/api/v1/catalog/duplicates")
    def api_v1_catalog_duplicates():
        try:
            from duplicate_candidates import detect_duplicates
            return jsonify({"groups": detect_duplicates()})
        except Exception:
            app.logger.exception("api_v1_catalog_duplicates_failed")
            return jsonify({"error": "duplicates_unavailable"}), 503

    @app.get("/api/v1/catalog/products/<int:product_id>/deletion")
    def api_v1_product_deletion_preview(product_id):
        from catalog_lifecycle import deletion_preview
        from shopping_match_queue import mutation_lock, DEFAULT_PATH
        try:
            with mutation_lock(DEFAULT_PATH, blocking=False):
                return jsonify(deletion_preview(product_id))
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except Exception:
            return jsonify({"error": "No se pudo verificar si el producto puede eliminarse. Conserva el archivado y vuelve a consultar."}), 503

    @app.delete("/api/v1/catalog/products/<int:product_id>")
    def api_v1_delete_catalog_product(product_id):
        from catalog_lifecycle import delete_archived
        from shopping_match_queue import mutation_lock, DEFAULT_PATH
        from stock_commands import execute_once, CommandConflict
        import re
        payload = request.get_json(silent=True)
        if (not isinstance(payload, dict) or not isinstance(payload.get('expected_name'), str)
                or payload.get('confirmation') != payload['expected_name'] or not payload['expected_name']
                or type(payload.get('delete_history', False)) is not bool
                or not isinstance(payload.get('token'), str) or not re.fullmatch(r'[a-f0-9]{64}', payload['token'])):
            return jsonify({"error": "Escribe el nombre exacto del producto y revisa su borrado antes de confirmar."}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            with mutation_lock(DEFAULT_PATH, blocking=False):
                def change():
                    try:
                        return {"status": 200, "body": delete_archived(product_id, payload['expected_name'], payload['token'], payload.get('delete_history', False))}
                    except barcode_stock.BarcodeError as exc:
                        return {"status": 409, "body": {"error": str(exc)}}
                result = execute_once(payload.get('operation_id'), {**payload, 'product_id': product_id, 'command': 'delete_archived'}, change)
            return jsonify(result['body']), result['status']
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except CommandConflict:
            return jsonify({"error": "No se ha reenviado el borrado. Comprueba el producto en Grocy antes de otra operación."}), 409
        except Exception:
            return jsonify({"error": "No se pudo confirmar el borrado. Comprueba Grocy y vuelve a abrir la ficha; no se ha repetido la operación."}), 502
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
        from merge_audit import merge_preview
        try:
            return jsonify(merge_preview(int(request.args.get('source_id', '0')), int(request.args.get('target_id', '0'))))
        except (ValueError, TypeError, barcode_stock.BarcodeError):
            return jsonify({"error": "No se pudo revisar la combinación. Selecciona dos productos y vuelve a consultar."}), 400
        except Exception:
            return jsonify({"error": "No se pudieron verificar todos los datos de Grocy para combinar."}), 503

    @app.post('/api/v1/catalog/products/merge')
    def api_v1_catalog_merge():
        import re
        from merge_audit import merge_products
        from shopping_match_queue import mutation_lock, DEFAULT_PATH
        from stock_commands import execute_once, CommandConflict
        payload = request.get_json(silent=True)
        if (not isinstance(payload, dict) or any(type(payload.get(key)) is not int or payload[key] <= 0 for key in ('source_id', 'target_id'))
                or payload['source_id'] == payload['target_id']
                or any(not isinstance(payload.get(key), str) or not payload[key] for key in ('expected_source', 'expected_target'))
                or payload.get('confirmation') != payload['expected_target']
                or not isinstance(payload.get('token'), str) or not re.fullmatch('[a-f0-9]{64}', payload['token'])):
            return jsonify({"error": "Revisa los productos y escribe el nombre exacto del que conservarás."}), 400
        if not lock.acquire(blocking=False): return jsonify({"error": "operation_in_progress"}), 409
        try:
            with mutation_lock(DEFAULT_PATH, blocking=False):
                def change():
                    try:
                        result = merge_products(payload['source_id'], payload['target_id'], payload['expected_source'], payload['expected_target'], payload['token'])
                        return {"status": 200, "body": result}
                    except barcode_stock.BarcodeError as exc:
                        return {"status": 409, "body": {"error": str(exc)}}
                result = execute_once(payload.get('operation_id'), {**payload, 'command': 'merge_products'}, change)
            return jsonify(result['body']), result['status']
        except BlockingIOError:
            return jsonify({"error": "operation_in_progress"}), 409
        except CommandConflict:
            return jsonify({"error": "No se ha reenviado la combinación. Comprueba Grocy antes de otra operación."}), 409
        except Exception:
            return jsonify({"error": "No se pudo confirmar la combinación. Comprueba ambos productos en Grocy antes de volver a intentarlo."}), 502
        finally: lock.release()

    @app.get('/api/v1/catalog/duplicates/differences')
    def api_v1_catalog_differences():
        from duplicate_review import differences
        try: return jsonify({"differences": differences()})
        except Exception: return jsonify({"error": "No se pudieron cargar las diferencias guardadas."}), 503

    @app.put('/api/v1/catalog/duplicates/differences')
    def api_v1_catalog_set_different():
        from duplicate_review import set_different
        payload = request.get_json(silent=True)
        if (not isinstance(payload, dict) or any(type(payload.get(key)) is not int or payload[key] <= 0 for key in ('left_id', 'right_id'))
                or payload['left_id'] == payload['right_id'] or any(not isinstance(payload.get(key), str) for key in ('left_name', 'right_name'))):
            return jsonify({"error": "Selecciona dos productos distintos y actualiza el análisis."}), 400
        if not lock.acquire(blocking=False): return jsonify({"error": "operation_in_progress"}), 409
        try:
            products = [barcode_stock.grocy('GET', f"objects/products/{payload[key + '_id']}") for key in ('left', 'right')]
            if any(int(product['id']) != payload[key + '_id'] or product['name'] != payload[key + '_name'] for key, product in zip(('left', 'right'), products)):
                return jsonify({"error": "Los productos han cambiado. Vuelve a analizar antes de decidir."}), 409
            set_different(*products)
            return jsonify({"saved": True})
        except Exception:
            return jsonify({"error": "No se pudo guardar la diferencia. Vuelve a consultar el análisis."}), 503
        finally: lock.release()

    @app.delete('/api/v1/catalog/duplicates/differences/<int:left_id>/<int:right_id>')
    def api_v1_catalog_undo_difference(left_id, right_id):
        from duplicate_review import undo_difference
        if not lock.acquire(blocking=False): return jsonify({"error": "operation_in_progress"}), 409
        try:
            undo_difference(left_id, right_id)
            return jsonify({"removed": True})
        except Exception: return jsonify({"error": "No se pudo deshacer la diferencia."}), 503
        finally: lock.release()
