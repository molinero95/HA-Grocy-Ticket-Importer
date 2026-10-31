"""Read-only adapters for the Alexa/Grocy shopping-list reconciler.

The Home Assistant API requires an explicit HA_TOKEN and HA_URL; never
log tokens. The add-on must not assume an ingress session is an API token.
No write operations are implemented here intentionally.
"""
import json
import os
import urllib.request

from importer import grocy


ALEXA_LIST = "todo.jaimolas95_gmail_com_lista_de_la_compra"


def ha_todo_items(entity_id=ALEXA_LIST, *, url=None, token=None):
    """Fetch live todo items using HA's todo.get_items service response.

    Only incomplete entries are eligible for synchronization. Completed
    history is ignored. The caller is responsible for securing the token.
    """
    url = (url or os.environ.get("HA_URL") or "").rstrip("/")
    token = token or os.environ.get("HA_TOKEN")
    if not url or not token:
        raise RuntimeError("HA_URL and HA_TOKEN are required")
    body = json.dumps({"entity_id": entity_id}).encode("utf-8")
    request = urllib.request.Request(
        url + "/api/services/todo/get_items?return_response",
        data=body, method="POST",
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    # HA service response may wrap service_response inside a response key.
    data = payload.get("service_response", payload)
    if entity_id not in data:
        raise ValueError("Missing Alexa list in HA response")
    items = data[entity_id].get("items")
    if not isinstance(items, list):
        raise ValueError("Invalid HA todo response")
    return [str(item["summary"]) for item in items
            if item.get("status") == "needs_action"]


def grocy_shopping_names():
    """Read Grocy default shopping list without modifying inventory."""
    products = grocy("GET", "objects/products")
    entries = grocy("GET", "objects/shopping_list")
    if not isinstance(products, list) or not isinstance(entries, list):
        raise ValueError("Invalid Grocy shopping-list response")
    by_id = {int(p["id"]): str(p["name"]) for p in products}
    names = []
    for item in entries:
        if int(item.get("shopping_list_id") or 1) != 1 or item.get("done"):
            continue
        pid = int(item.get("product_id") or 0)
        name = by_id.get(pid) if pid else str(item.get("note") or "").strip()
        if not name:
            raise ValueError("Unresolvable Grocy shopping item")
        names.append(name)
    return names
