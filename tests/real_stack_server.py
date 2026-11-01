"""Full-stack test fixture: actual Grocy 4.7.1, Flask APIs and real importer.

Only paid receipt extraction, public photo discovery and Home Assistant todo are substituted. Catalog,
stock, shopping, variants, receipt ledger and command journal use production code.
No user Home Assistant service or database is reachable from this fixture.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from grocy_instance import GrocyInstance


def start():
    instance = GrocyInstance(os.environ["GROCY_TEST_DIST"], os.environ.get("GROCY_TEST_PHP", "php")).start()
    units = instance.http("GET", "objects/quantity_units")
    if not any(unit["name"] == "Kilogram" for unit in units):
        instance.http("POST", "objects/quantity_units", {"name": "Kilogram", "name_plural": "Kilograms"})
    os.environ.update(GROCY_URL=instance.url, GROCY_API_KEY="disposable-test-only", GROCY_IMPORT_DB=str(instance.data / "ledger.sqlite3"),
                      RECEIPT_DATA_DIR=str(instance.data / "receipts"), PRODUCT_IMAGE_DIR=str(instance.data / "photos"),
                      GENERIC_CATALOG_DB=str(instance.data / "catalog.sqlite3"), ALEXA_MATCH_QUEUE_DB=str(instance.data / "queue.sqlite3"),
                      ALEXA_SHOPPING_LIST_ENTITY="todo.disposable", HA_URL="http://127.0.0.1:8767", HA_TOKEN="disposable", SHOPPING_SYNC_STATE=str(instance.data / "sync.json"),
                      WEB_PASSWORD="browser-test", WEB_SESSION_SECRET="full-stack-test-secret", HA_INGRESS_MODE="1",
                      FRONTEND_DIST_DIR=str(ROOT / "frontend" / "dist"))
    import web
    import barcode_stock
    import variant_catalog
    # Set the domain metadata path explicitly; no user's add-on paths are read.
    variant_catalog.CATALOG_DB = instance.data / "catalog.sqlite3"
    web.product_images.lookup_image = lambda code: None
    def extract(path):
        return {"merchant": "Disposable shop", "receipt_date": "2026-10-01", "total": 6,
                "source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                "items": [{"name": "Yogur de prueba", "quantity": 2, "unit_price": 3, "pieces_per_pack": 5, "purchase_units": "2", "ambiguous": False}]}
    web.extract.extract = extract
    piece = next(int(u["id"]) for u in instance.http("GET", "objects/quantity_units") if u["name"] == "Piece")
    catalog = {}
    for name in ("Leche de prueba", "Arroz redondo", "Arroz basmati", "Producto sin uso", "Pasta espirales", "Pasta espaguetis"):
        catalog[name] = barcode_stock.create_catalog_product(name, unit_id=piece, initial_stock="0")["product_id"]
    original_import = web.run_import
    def logged_import(rid, mode):
        result = original_import(rid, mode)
        if result.returncode:
            print("Fixture importer failure:", result.stderr, flush=True)
        return result
    web.run_import = logged_import
    import shopping_match_queue
    shopping_match_queue.refresh(shopping_match_queue.DEFAULT_PATH, ["Arroz"], [{"id": catalog[name], "name": name} for name in ("Arroz redondo", "Arroz basmati")])
    from flask import request
    alexa = [{"summary": "Arroz", "uid": "test-arroz", "status": "needs_action"}, {"summary": "Pasta", "uid": "test-pasta", "status": "needs_action"}]
    @web.app.post("/api/services/todo/<service>")
    def fixture_todo(service):
        payload = request.get_json()
        if service == "get_items":
            return {"service_response": {"todo.disposable": {"items": alexa}}}
        if service == "add_item":
            alexa.append({"summary": payload["item"], "uid": payload["item"], "status": "needs_action"})
        elif service == "remove_item":
            alexa[:] = [row for row in alexa if row["uid"] != payload["item"] and row["summary"] != payload["item"]]
        return {}
    # The local todo stub is an independent API with its own bearer token,
    # so it is exempt from browser-session CSRF only inside this fixture.
    production_protect = web.app.before_request_funcs[None][0]
    def fixture_protect():
        if request.path.startswith("/api/services/todo/") and request.headers.get("Authorization") == "Bearer disposable":
            return None
        return production_protect()
    web.app.before_request_funcs[None][0] = fixture_protect
    @web.app.post("/api/v1/__test/sync")
    def fixture_sync():
        import shopping_sync_worker
        result = shopping_sync_worker.run_once(dry_run=False)
        return result
    @web.app.get("/__test/photo.png")
    def fixture_image():
        import io
        from PIL import Image
        output = io.BytesIO(); Image.new("RGB", (30, 30), "red").save(output, "PNG")
        return web.app.response_class(output.getvalue(), mimetype="image/png")
    @web.app.get("/__test/info")
    def fixture_info():
        return {"products": catalog, "grocy": instance.http("GET", "system/info")}
    @web.app.post("/api/v1/__test/restart")
    def fixture_restart():
        instance.stop()
        instance.start()
        return {"restarted": True}
    return instance, web


if __name__ == "__main__":
    instance, web = start()
    try:
        if "--check" in sys.argv:
            import unittest
            from real_stack_tests import RealStackTests
            RealStackTests.instance = instance
            RealStackTests.web = web
            result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RealStackTests))
            raise SystemExit(0 if result.wasSuccessful() else 1)
        web.app.run(host="127.0.0.1", port=8767, threaded=True)
    finally:
        instance.close()
