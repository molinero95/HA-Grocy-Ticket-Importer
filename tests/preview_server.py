"""Disposable browser-test server. All Grocy/Alexa I/O is replaced locally."""
import copy
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(WEB_PASSWORD="browser-test", WEB_SESSION_SECRET="local-browser-test-secret", FRONTEND_DIST_DIR=str(ROOT / "frontend" / "dist"))
state = tempfile.TemporaryDirectory()
os.environ.update(PRODUCT_IMAGE_DIR=state.name, STOCK_COMMAND_DB=state.name + "/commands.sqlite3")
import web

prefix = "/api/hassio_ingress/browser-test"
web.INGRESS_MODE = "--ingress" in sys.argv
if web.INGRESS_MODE:
    wrapped = web.app.wsgi_app
    def ingress_proxy(environ, start_response):
        if environ["PATH_INFO"].startswith(prefix):
            environ["PATH_INFO"] = environ["PATH_INFO"][len(prefix):] or "/"
            environ["HTTP_X_INGRESS_PATH"] = prefix
        return wrapped(environ, start_response)
    web.app.wsgi_app = ingress_proxy

products = [
    {"id": 1, "name": "Tomate de nombre muy largo para comprobar las columnas en pantallas móviles", "amount": "2", "unit": "kg", "shopping_amount": "0", "shopping_step": "0.1", "shopping_unit": "kg", "shopping_can_subtract": False, "image_url": None},
    {"id": 2, "name": "Leche", "amount": "3", "unit": "ud.", "shopping_amount": "1", "shopping_step": "1", "shopping_unit": "ud.", "shopping_can_subtract": True, "image_url": None},
]
shopping = [{"id": 1, "name": products[0]["name"], "amount": 1, "unit": "kg", "done": False, "product_id": 1, "image_url": None}, {"id": 2, "name": "Leche", "amount": 1, "unit": "ud.", "done": False, "product_id": 2, "image_url": None}]
def unexpected_io(*args, **kwargs):
    raise AssertionError("Browser fixture attempted external Grocy I/O")
web.barcode_stock.grocy = unexpected_io
web.barcode_stock.inventory_with_shopping = lambda: copy.deepcopy(products)
web.barcode_stock.shopping_list_snapshot = lambda: copy.deepcopy(shopping)
web.shopping_match_queue.pending = lambda path: []
web.barcode_stock.find_product = lambda code: {"id": 2} if code == "8412345678901" else None

def step(pid, direction):
    item = products[pid - 1]
    item["shopping_amount"] = item["shopping_step"] if direction == "plus" else "0"
    item["shopping_can_subtract"] = direction == "plus"
    return {"amount": item["shopping_amount"]}
web.barcode_stock.change_shopping_quantity = step

def toggle(pid, done):
    shopping[pid - 1]["done"] = done
web.barcode_stock.update_shopping_list_item = toggle

if __name__ == "__main__":
    web.app.run(host="127.0.0.1", port=8766 if web.INGRESS_MODE else 8765, threaded=True)
