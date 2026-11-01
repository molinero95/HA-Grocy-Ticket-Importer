"""Trusted product-photo discovery and local uploads for the React client."""
import io
import os
from pathlib import Path

from flask import jsonify, request
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024


def image_directory():
    return Path(os.environ.get("PRODUCT_IMAGE_DIR", str(Path(__file__).resolve().parent / "runtime" / "product_images")))


def local_image_url(product_id):
    path = image_directory() / f"{int(product_id)}.jpg"
    if path.is_file():
        # Replacing a photo must invalidate the browser's one-hour image cache.
        return f"product/{int(product_id)}/photo/local?v={path.stat().st_mtime_ns}"
    return None


def register_photo_routes(app, barcode_stock, lock):
    import product_images

    @app.get("/api/v1/photos/<barcode>")
    def api_v1_photo_lookup(barcode):
        try:
            found = product_images.lookup_image(barcode)
            return jsonify({"photo": found})
        except barcode_stock.BarcodeError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.warning("api_v1_photo_lookup_unavailable")
            return jsonify({"error": "No se pudo consultar la fotografía. Puedes continuar sin ella."}), 503

    @app.post("/api/v1/catalog/products/<int:product_id>/photo-lookup")
    def api_v1_save_discovered_photo(product_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or type(payload.get("replace", False)) is not bool:
            return jsonify({"error": "invalid_payload"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        try:
            code = barcode_stock.validate_barcode(payload.get("barcode"))
            product = barcode_stock.product_detail(product_id)
            if code not in product["barcodes"]:
                return jsonify({"error": "El código no pertenece al producto"}), 409
            existing = local_image_url(product_id) or product.get("image_url")
            if existing and not payload.get("replace", False):
                return jsonify({"saved": False, "image_url": existing, "preserved": True})
            # Never accept an image URL from a browser or persist an unassociated code.
            found = product_images.lookup_image(code)
            url = product_images.safe_image_url(found.get("image_url")) if found else None
            if not url:
                return jsonify({"saved": False, "image_url": existing})
            barcode_stock.save_product_photo(product_id, url)
            # Keep user uploads; they take precedence over a public reference.
            return jsonify({"saved": True, "image_url": local_image_url(product_id) or url})
        except (barcode_stock.BarcodeError, TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.warning("api_v1_photo_save_unavailable")
            return jsonify({"error": "No se pudo guardar la foto. El código y el stock se conservan."}), 503
        finally:
            lock.release()

    @app.post("/api/v1/catalog/products/<int:product_id>/photo")
    def api_v1_upload_catalog_photo(product_id):
        uploaded = request.files.get("photo")
        if not uploaded or not uploaded.filename:
            return jsonify({"error": "Selecciona una fotografía"}), 400
        if not lock.acquire(blocking=False):
            return jsonify({"error": "operation_in_progress"}), 409
        temporary = None
        try:
            barcode_stock.product_detail(product_id)
            raw = uploaded.read(MAX_IMAGE_BYTES + 1)
            if len(raw) > MAX_IMAGE_BYTES:
                return jsonify({"error": "La imagen supera 8 MiB"}), 413
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in ("JPEG", "PNG", "WEBP"):
                    return jsonify({"error": "Formato no admitido. Usa JPG, PNG o WebP"}), 400
                # Bound decoded memory as well as compressed upload size.
                if source.width * source.height > 25_000_000:
                    return jsonify({"error": "La imagen supera 25 megapíxeles"}), 400
                image = ImageOps.exif_transpose(source)
                image.thumbnail((1200, 1200))
                directory = image_directory()
                directory.mkdir(parents=True, exist_ok=True)
                temporary = directory / f"{product_id}.tmp"
                image.convert("RGB").save(temporary, format="JPEG", quality=85)
                temporary.replace(directory / f"{product_id}.jpg")
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, barcode_stock.BarcodeError):
            return jsonify({"error": "Imagen inválida o producto inexistente"}), 400
        except Exception:
            app.logger.exception("api_v1_catalog_photo_failed")
            return jsonify({"error": "No se pudo guardar la fotografía"}), 502
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
            lock.release()
        return jsonify({"saved": True, "photo_url": local_image_url(product_id)})
