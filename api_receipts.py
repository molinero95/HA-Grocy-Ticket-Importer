"""Receipt upload and extraction API; never imports into Grocy on upload."""
import json
import hashlib
import secrets
from functools import wraps
from decimal import Decimal, InvalidOperation
from pathlib import Path
from flask import jsonify, request, session
from werkzeug.utils import secure_filename


def register_receipt_routes(app, data_dir, allowed, extract_module, run_import, lock):
    def exclusive_preview(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if not lock.acquire(blocking=False):
                return jsonify({"error": "import_in_progress"}), 409
            try:
                return function(*args, **kwargs)
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

    @app.post("/api/v1/receipts/<receipt_id>/preview")
    @exclusive_preview
    def api_v1_preview_receipt(receipt_id):
        if session.get("receipt_id") != receipt_id or len(receipt_id) != 32 or any(c not in "0123456789abcdef" for c in receipt_id):
            return jsonify({"error": "receipt_not_found"}), 404
        path = data_dir / (receipt_id + ".json")
        if not path.is_file():
            return jsonify({"error": "receipt_not_found"}), 404
        session.pop("previewed", None)
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
                qty = Decimal(str(edited.get("purchase_units", original["quantity"])))
                factor = Decimal(str(edited.get("pieces_per_pack", original.get("pieces_per_pack", 1))))
                if (not qty.is_finite() or qty <= 0 or qty != Decimal(str(original["quantity"]))
                        or not factor.is_finite() or factor != factor.to_integral_value() or not 1 <= factor <= 1000):
                    raise ValueError("invalid_quantity_or_pack")
                original["name"] = name.strip()
                original["purchase_units"] = str(qty)
                original["pieces_per_pack"] = int(factor)
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
        session["previewed"] = receipt_id
        session["previewed_digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return jsonify({"receipt_id": receipt_id, "preview": result.stdout, "ready_to_commit": True})

    @app.post("/api/v1/receipts/<receipt_id>/commit")
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
        if not lock.acquire(blocking=False):
            return jsonify({"error": "import_in_progress"}), 409
        try:
            # A preview may have edited the file while this request waited for
            # the lock. Validate the exact bytes again before any stock write.
            if session.get("previewed_digest") != hashlib.sha256(path.read_bytes()).hexdigest():
                return jsonify({"error": "receipt_changed_since_preview"}), 409
            marker = data_dir / (receipt_id + ".commit-started")
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
            if result.returncode:
                return jsonify({"error": "receipt_commit_uncertain", "details": "La importación se interrumpió. Comprueba Grocy antes de reintentar.", "output": result.stdout[-1200:]}), 502
            return jsonify({"receipt_id": receipt_id, "status": "committed", "output": result.stdout})
        finally:
            lock.release()
