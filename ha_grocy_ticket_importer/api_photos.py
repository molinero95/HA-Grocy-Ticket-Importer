"""Trusted product-photo discovery and local uploads for the React client."""
import io
import os
import threading
import product_recognition
from pathlib import Path

from flask import jsonify, request, session
from PIL import Image, ImageOps, UnidentifiedImageError

IDENTIFY_LOCK = threading.Lock()

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

    @app.post("/api/v1/photos/identify")
    def api_v1_identify_product_photo():
        if request.form.get('consent') != 'true':
            return jsonify({'error': 'Confirma el envío de la fotografía a OpenAI'}), 400
        uploaded = request.files.get('photo')
        if not uploaded or not uploaded.filename:
            return jsonify({'error': 'Selecciona una fotografía completa del producto'}), 400
        try:
            value = request.form.get('barcode', '').strip()
            code = barcode_stock.validate_barcode(value) if value else ''
        except (barcode_stock.BarcodeError, ValueError):
            return jsonify({'error': 'Revisa el código de barras'}), 400
        if not IDENTIFY_LOCK.acquire(blocking=False):
            return jsonify({'error': 'Hay otro análisis de fotografía en curso'}), 409
        try:
            raw = uploaded.read(MAX_IMAGE_BYTES + 1)
            if len(raw) > MAX_IMAGE_BYTES:
                return jsonify({'error': 'La imagen supera 8 MiB'}), 413
            return jsonify({'suggestion': product_recognition.identify(raw, code)})
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception:
            # Do not log photo bytes, labels, paid-provider response bodies or keys.
            return jsonify({'error': 'No se pudo analizar la foto. Puedes completar el nombre manualmente.'}), 503
        finally:
            IDENTIFY_LOCK.release()

    @app.post("/api/v1/photos/discover")
    def api_v1_discover_product():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or payload.get("consent") is not True:
            return jsonify({"error": "Confirma la búsqueda del nombre con OpenAI"}), 400
        name, code = payload.get("name"), payload.get("barcode", "")
        if not isinstance(name, str) or not 3 <= len(name.strip()) <= 200 or not isinstance(code, str):
            return jsonify({"error": "Escribe un nombre de entre 3 y 200 caracteres"}), 400
        try:
            code = barcode_stock.validate_barcode(code) if code.strip() else ""
        except (ValueError, barcode_stock.BarcodeError):
            return jsonify({"error": "Revisa el código de barras"}), 400
        product_id = payload.get('product_id')
        if product_id is not None and (type(product_id) is not int or product_id <= 0 or code):
            return jsonify({'error': 'invalid_payload'}), 400
        if not IDENTIFY_LOCK.acquire(blocking=False):
            return jsonify({"error": "Hay otra búsqueda o análisis de IA en curso"}), 409
        try:
            from itsdangerous import URLSafeTimedSerializer
            binding = {}
            if product_id is not None:
                product = barcode_stock.product_detail(product_id)
                if product['name'] != name.strip():
                    return jsonify({'error': 'El nombre ha cambiado. Actualiza la ficha antes de buscar.'}), 409
                binding = {'product_id': product_id,
                           'expected_image_url': local_image_url(product_id) or product.get('image_url')}
            result = product_recognition.discover(name, code)
            signer = URLSafeTimedSerializer(app.secret_key, salt="product-name-photo-v1")
            for candidate in result['candidates']:
                candidate['discovery_token'] = signer.dumps({'name': name.strip(), 'context_code': code,
                    'candidate_code': candidate['barcode'], 'source_url': candidate['search_source_url'], 'session': session.get('csrf'), **binding})
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            return jsonify({"error": "No se pudo buscar con IA. Puedes continuar manualmente."}), 503
        finally:
            IDENTIFY_LOCK.release()

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

    @app.post("/api/v1/catalog/products/<int:product_id>/photo-discovery")
    def api_v1_save_name_photo(product_id):
        from itsdangerous import URLSafeTimedSerializer, BadData
        payload = request.get_json(silent=True)
        if (not isinstance(payload, dict) or not isinstance(payload.get('token'), str) or len(payload['token']) > 8192
                or type(payload.get('replace', False)) is not bool):
            return jsonify({'error': 'Vuelve a elegir una imagen de la búsqueda'}), 400
        try:
            choice = URLSafeTimedSerializer(app.secret_key, salt="product-name-photo-v1").loads(payload['token'], max_age=1800)
            if choice.get('session') != session.get('csrf'): raise ValueError('Otra sesión')
        except (BadData, ValueError, TypeError):
            return jsonify({'error': 'La selección de imagen ha caducado. Vuelve a buscar.'}), 409
        if not lock.acquire(blocking=False): return jsonify({'error': 'operation_in_progress'}), 409
        try:
            product = barcode_stock.product_detail(product_id)
            existing = local_image_url(product_id) or product.get('image_url')
            editing = choice.get('product_id') is not None
            if editing:
                if (choice['product_id'] != product_id or product['name'] != choice['name']
                        or existing != choice.get('expected_image_url')):
                    return jsonify({'error': 'La ficha o su fotografía han cambiado. Actualiza y vuelve a buscar.'}), 409
                if existing and not payload.get('replace', False):
                    return jsonify({'saved': False, 'preserved': True})
            else:
                code = choice['context_code'] or choice['candidate_code']
                if product['name'] != choice['name'] or code not in product['barcodes']:
                    return jsonify({'error': 'El nombre o el código han cambiado. Vuelve a elegir la imagen.'}), 409
                if existing: return jsonify({'saved': False, 'preserved': True})
            found = product_images.verify_discovered_product(choice['source_url'])
            image = product_images.safe_image_url(found.get('image_url')) if found and found['barcode'] == choice['candidate_code'] else None
            if not image: return jsonify({'saved': False})
            barcode_stock.save_product_photo(product_id, image)
            if editing:
                # Keep the previous local image privately; only retire it after URL persistence succeeds.
                local = image_directory() / f"{product_id}.jpg"
                if local.exists():
                    import time
                    local.rename(image_directory() / f"{product_id}.previous-{time.time_ns()}.jpg")
            return jsonify({'saved': True, 'image_url': image})
        except Exception:
            return jsonify({'error': 'El producto se conserva. No se pudo guardar la imagen seleccionada.'}), 503
        finally: lock.release()

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
