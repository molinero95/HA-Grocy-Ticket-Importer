"""Wake shopping sync on Home Assistant todo events; polling remains a fallback."""
import json
import os
import threading
import time

import websocket


def listen(wake: threading.Event):
    entity = os.environ.get("ALEXA_SHOPPING_LIST_ENTITY", "")
    token = os.environ.get("HA_TOKEN") or os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HASSIO_TOKEN")
    base = os.environ.get("HA_URL", "http://homeassistant:8123").rstrip("/")
    if not entity or not token:
        return
    ws_url = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/api/websocket"
    while True:
        try:
            with websocket.create_connection(ws_url, timeout=30, http_proxy_host=None, http_proxy_port=None) as ws:
                if json.loads(ws.recv()).get("type") != "auth_required":
                    raise RuntimeError("Unexpected HA websocket greeting")
                ws.send(json.dumps({"type": "auth", "access_token": token}))
                if json.loads(ws.recv()).get("type") != "auth_ok":
                    raise RuntimeError("Home Assistant websocket authentication failed")
                for i, event_type in enumerate(("state_changed", "call_service"), start=1):
                    ws.send(json.dumps({"id": i, "type": "subscribe_events", "event_type": event_type}))
                    result = json.loads(ws.recv())
                    if not result.get("success"):
                        raise RuntimeError("HA event subscription failed")
                ws.settimeout(None)
                print("Shopping sync HA event listener connected", flush=True)
                while True:
                    message = json.loads(ws.recv())
                    if message.get("type") != "event":
                        continue
                    event = message.get("event", {})
                    data = event.get("data", {})
                    if event.get("event_type") == "state_changed" and data.get("entity_id") == entity:
                        wake.set()
                    elif (event.get("event_type") == "call_service" and
                          data.get("domain") == "todo" and
                          entity in str(data.get("service_data", {}).get("entity_id", ""))):
                        wake.set()
        except Exception as exc:
            # Diagnostic category only; never expose URLs, tokens or remote error bodies.
            category = type(exc).__name__
            if isinstance(exc, websocket.WebSocketBadStatusException):
                category += " HTTP " + str(exc.status_code)
            print("Shopping sync HA event listener disconnected (" + category + "); retrying", flush=True)
            time.sleep(15)
