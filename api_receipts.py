"""Receipt upload and extraction API; never imports into Grocy on upload."""
import json
import secrets
from pathlib import Path
from flask import jsonify, request, session
from werkzeug.utils import secure_filename


def register_receipt_routes(app, data_dir, allowed, extract_module):
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
        return jsonify({"receipt_id": receipt_id, "receipt": receipt}), 201

    @app.get("/api/v1/receipts/<receipt_id>")
    def api_v1_get_receipt(receipt_id):
        if session.get("receipt_id") != receipt_id or len(receipt_id) != 32 or any(c not in "0123456789abcdef" for c in receipt_id):
            return jsonify({"error": "receipt_not_found"}), 404
        path = data_dir / (receipt_id + ".json")
        if not path.is_file():
            return jsonify({"error": "receipt_not_found"}), 404
        return jsonify({"receipt_id": receipt_id, "receipt": json.loads(path.read_text(encoding="utf-8"))})
