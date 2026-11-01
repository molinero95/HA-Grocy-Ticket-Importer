"""Receipt upload and extraction API; never imports into Grocy on upload."""
import json
import hashlib
import secrets
from functools import wraps
from shopping_match_queue import mutation_lock, DEFAULT_PATH
from decimal import InvalidOperation
from pathlib import Path
from flask import jsonify, request, session
from werkzeug.utils import secure_filename
from receipt_review import validate_review, mappings, has_review, key
import importer


def register_receipt_routes(app, data_dir, allowed, extract_module, run_import, lock):
    def exclusive_preview(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if not lock.acquire(blocking=False):
                return jsonify({"error": "import_in_progress"}), 409
            try:
                try:
                    with mutation_lock(DEFAULT_PATH, blocking=False):
                        return function(*args, **kwargs)
                except BlockingIOError:
                    return jsonify({"error": "import_in_progress"}), 409
            finally:
                lock.release()
        return wrapped

    @app.post("/api/v1/receipts")
    def api_v1_upload_receipt():
        uploads = [file for file in request.files.getlist("ticket") if file and file.filename]
        if len(uploads) != 1:
            return jsonify({"error": "single_receipt_required"}), 400
        upload = uploads[0]
        extension = Path(secure_filename(upload.filename or "")).suffix.lower()
        if extension not in allowed:
            return jsonify({"error": "unsupported_receipt_format"}), 400
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        receipt_id = secrets.token_hex(16)
        source = data_dir / (receipt_id + extension)
        try:
            upload.save(source)
            receipt = extract_module.extract(source)
            (data_dir / (receipt_id + ".json")).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            app.logger.exception("api_v1_receipt_extraction_failed")
            return jsonify({"error": "receipt_extraction_failed"}), 502
        finally:
            source.unlink(missing_ok=True)
        session["receipt_id"] = receipt_id
        session.pop("previewed", None)
        session.pop("previewed_digest", None)
        return jsonify({"receipt_id": receipt_id, "receipt": receipt}), 201

    @app.get("/api/v1/receipts/<receipt_id>")
    def api_v1_get_receipt(receipt_id):
        if session.get("receipt_id") != receipt_id or len(receipt_id) != 32 or any(c not in "0123456789abcdef" for c in receipt_id):
            return jsonify({"error": "receipt_not_found"}), 404
        path = data_dir / (receipt_id + ".json")
        if not path.is_file():
            return jsonify({"error": "receipt_not_found"}), 404
        return jsonify({"receipt_id": receipt_id, "receipt": json.loads(path.read_text(encoding="utf-8"))})

    @app.get("/api/v1/receipts/<receipt_id>/review-context")
    def api_v1_receipt_review_context(receipt_id):
        if session.get("receipt_id") != receipt_id or len(receipt_id) != 32 or any(c not in "0123456789abcdef" for c in receipt_id):
            return jsonify({"error": "receipt_not_found"}), 404
        path = data_dir / (receipt_id + ".json")
        if not path.is_file():
            return jsonify({"error": "receipt_not_found"}), 404
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
            products = importer.grocy('GET', 'objects/products')
            units = {int(u['id']): u['name'].casefold() for u in importer.grocy('GET', 'objects/quantity_units')}
            conversions = importer.grocy('GET', 'objects/quantity_unit_conversions')
            catalog = []
            for p in products:
                if str(p.get('active', 1)).lower() not in ('1', 'true'):
                    continue
                label = units.get(int(p['qu_id_stock']), '')
                unit = 'piece' if label in ('piece', 'pieces', 'unidad', 'unidades') else 'kg' if label in ('kg', 'kilogram', 'kilograms', 'kilogramo', 'kilogramos') else None
                if unit is None:
                    continue
                stock_id, purchase_id = int(p['qu_id_stock']), int(p.get('qu_id_purchase') or p['qu_id_stock'])
                if purchase_id != stock_id and (unit != 'piece' or units.get(purchase_id) not in ('pack', 'paquete', 'envase')):
                    continue
                try:
                    from purchase_units import purchase_factor
                    factor = purchase_factor(lambda method, route: conversions, int(p['id']), purchase_id, stock_id)
                    if factor != factor.to_integral_value() or not 1 <= factor <= 1000:
                        continue
                except (ValueError, ArithmeticError):
                    continue
                catalog.append({'id': int(p['id']), 'name': p['name'], 'stock_unit': unit, 'pieces_per_pack': int(factor)})
            saved = mappings(importer.DB_PATH, receipt.get('merchant', ''))
            active = {p['id']: p for p in catalog}
            for value in saved.values():
                current = active.get(value['product_id'])
                value['stale'] = not current or current['stock_unit'] != value['stock_unit'] or current['pieces_per_pack'] != value['pieces_per_pack']
            return jsonify({'products': sorted(catalog, key=lambda p: p['name'].casefold()), 'mappings': saved, 'line_mappings': [saved.get(key(item.get('original_name', item['name']))) for item in receipt['items']]})
        except Exception:
            app.logger.exception('receipt_review_context_failed')
            return jsonify({'error': 'No se pudo consultar el catálogo del ticket'}), 503

    @app.post("/api/v1/receipts/<receipt_id>/preview")
    @exclusive_preview
    def api_v1_preview_receipt(receipt_id):
        if session.get("receipt_id") != receipt_id or len(receipt_id) != 32 or any(c not in "0123456789abcdef" for c in receipt_id):
            return jsonify({"error": "receipt_not_found"}), 404
        path = data_dir / (receipt_id + ".json")
        if not path.is_file():
            return jsonify({"error": "receipt_not_found"}), 404
        session.pop("previewed", None)
        session.pop("previewed_digest", None)
        if (data_dir / (receipt_id + ".commit-started")).exists():
            return jsonify({"error": "receipt_already_submitted"}), 409
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            return jsonify({"error": "invalid_items"}), 400
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if len(payload["items"]) != len(receipt.get("items", [])):
            return jsonify({"error": "item_count_mismatch"}), 400
        try:
            for original, edited in zip(receipt["items"], payload["items"]):
                if not isinstance(edited, dict):
                    raise ValueError("invalid_item")
                name = edited.get("name")
                if not isinstance(name, str) or not 0 < len(name.strip()) <= 200:
                    raise ValueError("invalid_name")
                reviewed = {**original, **{key: edited[key] for key in ('purchase_units', 'pieces_per_pack', 'stock_unit', 'product_mode', 'product_id', 'remember_product', 'unit_confirmed') if key in edited}}
                qty, factor = validate_review(reviewed)
                original.setdefault("original_name", original["name"])
                original["name"] = name.strip()
                original["purchase_units"] = str(qty)
                original["pieces_per_pack"] = factor
                for key in ('stock_unit', 'product_mode', 'product_id', 'remember_product', 'unit_confirmed'):
                    if key in edited:
                        original[key] = edited[key]
        except (ValueError, InvalidOperation, TypeError, KeyError):
            return jsonify({"error": "invalid_receipt_items"}), 400
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            result = run_import(receipt_id, "--dry-run")
        except Exception:
            app.logger.exception("api_v1_receipt_preview_failed")
            return jsonify({"error": "receipt_preview_failed"}), 502
        if result.returncode:
            return jsonify({"error": "receipt_preview_rejected", "details": result.stderr[-1200:]}), 400
        if has_review(result.stdout):
            return jsonify({"receipt_id": receipt_id, "preview": result.stdout, "ready_to_commit": False})
        session["previewed"] = receipt_id
        session["previewed_digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
        session["previewed_plan"] = hashlib.sha256(result.stdout.encode()).hexdigest()
        return jsonify({"receipt_id": receipt_id, "preview": result.stdout, "ready_to_commit": True})

    @app.post("/api/v1/receipts/<receipt_id>/commit")
    @exclusive_preview
    def api_v1_commit_receipt(receipt_id):
        if session.get("receipt_id") != receipt_id or len(receipt_id) != 32 or any(c not in "0123456789abcdef" for c in receipt_id):
            return jsonify({"error": "receipt_not_found"}), 404
        if session.get("previewed") != receipt_id:
            return jsonify({"error": "preview_required"}), 403
        path = data_dir / (receipt_id + ".json")
        if not path.is_file():
            return jsonify({"error": "receipt_not_found"}), 404
        if session.get("previewed_digest") != hashlib.sha256(path.read_bytes()).hexdigest():
            session.pop("previewed", None)
            session.pop("previewed_digest", None)
            return jsonify({"error": "receipt_changed_since_preview"}), 409
        # Re-audit the current catalog/conversions under the shared worker lock.
        marker = data_dir / (receipt_id + ".commit-started")
        if marker.exists():
            return jsonify({"error": "receipt_already_submitted"}), 409
        try:
            preflight = run_import(receipt_id, "--dry-run")
        except Exception:
            return jsonify({"error": "receipt_preview_failed"}), 502
        if (preflight.returncode or has_review(preflight.stdout)
                or (session.get("previewed_plan") and session["previewed_plan"] != hashlib.sha256(preflight.stdout.encode()).hexdigest())):
            session.pop("previewed", None)
            session.pop("previewed_digest", None)
            return jsonify({"error": "receipt_preview_rejected", "details": "El catálogo o las unidades han cambiado. Revisa y simula otra vez."}), 409
        try:
            with marker.open("x", encoding="utf-8") as handle:
                handle.write("started\\n")
        except FileExistsError:
            return jsonify({"error": "receipt_already_submitted", "details": "Comprueba el stock antes de reintentar."}), 409
        session.pop("previewed", None)
        try:
            result = run_import(receipt_id, "--commit")
        except Exception:
            app.logger.exception("api_v1_receipt_commit_uncertain")
            return jsonify({"error": "receipt_commit_uncertain", "details": "Comprueba Grocy antes de reintentar."}), 502
        if result.returncode or has_review(result.stdout):
            return jsonify({"error": "receipt_commit_uncertain", "details": "La importación se interrumpió. Comprueba Grocy antes de reintentar.", "output": result.stdout[-1200:]}), 502
        return jsonify({"receipt_id": receipt_id, "status": "committed", "output": result.stdout})
