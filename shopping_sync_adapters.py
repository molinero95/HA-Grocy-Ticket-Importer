"""Home Assistant Alexa and Grocy shopping list adapters.

Use Supervisor's scoped Home Assistant API token inside the add-on.
All writes are idempotent by reading fresh snapshots first.
"""
import json
import os
import urllib.request

from importer import grocy
from shopping_sync import normalize

ALEXA_LIST = "todo.jaimolas95_gmail_com_lista_de_la_compra"


def ha_service(service, body, *, url=None, token=None):
    url = (url or os.environ.get("HA_URL") or "http://supervisor/core").rstrip("/")
    token = token or os.environ.get("HA_TOKEN") or os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Home Assistant API token unavailable")
    request = urllib.request.Request(
        url + "/api/services/todo/" + service + ("?return_response" if service == "get_items" else ""),
        data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def alexa_items():
    response = ha_service("get_items", {"entity_id": ALEXA_LIST})
    data = response.get("service_response", response)
    if ALEXA_LIST not in data or not isinstance(data[ALEXA_LIST].get("items"), list):
        raise ValueError("Invalid Alexa list response")
    return [item for item in data[ALEXA_LIST]["items"]
            if item.get("status") == "needs_action"]


def ha_todo_items():
    return [str(item["summary"]) for item in alexa_items()]


def add_alexa(name):
    if normalize(name) not in {normalize(item["summary"]) for item in alexa_items()}:
        ha_service("add_item", {"entity_id": ALEXA_LIST, "item": name})


def remove_alexa(name):
    for item in alexa_items():
        if normalize(item["summary"]) == normalize(name):
            ha_service("remove_item", {"entity_id": ALEXA_LIST,
                                       "item": item.get("uid") or item["summary"]})


def grocy_entries():
    products = grocy("GET", "objects/products")
    entries = grocy("GET", "objects/shopping_list")
    if not isinstance(products, list) or not isinstance(entries, list):
        raise ValueError("Invalid Grocy shopping-list response")
    by_id = {int(p["id"]): str(p["name"]) for p in products}
    result = []
    for entry in entries:
        if int(entry.get("shopping_list_id") or 1) != 1 or entry.get("done"):
            continue
        pid = int(entry.get("product_id") or 0)
        name = by_id.get(pid) if pid else str(entry.get("note") or "").strip()
        if not name:
            raise ValueError("Unresolvable Grocy shopping item")
        result.append((name, entry))
    return result


def grocy_shopping_names():
    return [name for name, _ in grocy_entries()]


def add_grocy(name):
    if normalize(name) in {normalize(n) for n, _ in grocy_entries()}:
        return
    products = grocy("GET", "objects/products")
    matches = [p for p in products if normalize(p["name"]) == normalize(name)]
    if len(matches) > 1:
        raise ValueError("Ambiguous Grocy product: " + name)
    if matches:
        p = matches[0]
        grocy("POST", "stock/shoppinglist/add-product",
              {"product_id": int(p["id"]), "list_id": 1,
               "product_amount": 1, "qu_id": int(p["qu_id_stock"])})
    else:
        # Grocy supports free-text shopping list notes without catalog products.
        grocy("POST", "objects/shopping_list",
              {"shopping_list_id": 1, "note": name, "amount": 1})


def remove_grocy(name):
    for existing_name, entry in grocy_entries():
        if normalize(existing_name) == normalize(name):
            grocy("DELETE", "objects/shopping_list/" + str(int(entry["id"])))
