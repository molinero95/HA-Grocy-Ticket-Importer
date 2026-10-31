"""Wake the shopping worker from HA events; polling is always the fallback."""
import json
import os
import threading
import time
from urllib.parse import urlsplit, urlunsplit

import websocket


def websocket_url():
    # Supervisor's /core REST proxy does not reliably support WebSocket upgrades.
    # Use the Core endpoint unless an explicit WebSocket URL is supplied.
    base = (os.environ.get("HA_WS_URL") or "http://homeassistant:8123").rstrip("/")
    parts = urlsplit(base)
    if parts.scheme not in ("http", "https", "ws", "wss") or not parts.netloc:
        raise ValueError("Invalid HA websocket endpoint")
    scheme = {"http": "ws", "https": "wss"}.get(parts.scheme, parts.scheme)
    path = parts.path.rstrip("/")
    if not path.endswith("/api/websocket"):
        path += "/api/websocket"
    return urlunsplit((scheme, parts.netloc, path, "", ""))


def handle_event(message, entity, wake):
    if message.get("type") != "event":
        return
    event = message.get("event") or {}
    data = event.get("data") or {}
    if event.get("event_type") == "state_changed" and data.get("entity_id") == entity:
        wake.set()
    elif event.get("event_type") == "call_service" and data.get("domain") == "todo":
        target = data.get("service_data") or {}
        ids = target.get("entity_id") or (data.get("target") or {}).get("entity_id") or []
        if isinstance(ids, str):
            ids = [ids]
        if entity in ids:
            wake.set()


def listen(wake: threading.Event):
    entity = os.environ.get("ALEXA_SHOPPING_LIST_ENTITY", "")
    token = os.environ.get("HA_TOKEN") or os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HASSIO_TOKEN")
    if not entity or not token:
        print("Shopping sync HA events disabled: missing entity or token", flush=True)
        return
    while True:
        try:
            ws = websocket.create_connection(websocket_url(), timeout=30, http_proxy_host=None, http_proxy_port=None)
            try:
                if json.loads(ws.recv()).get("type") != "auth_required":
                    raise RuntimeError("UnexpectedGreeting")
                ws.send(json.dumps({"type": "auth", "access_token": token}))
                if json.loads(ws.recv()).get("type") != "auth_ok":
                    raise RuntimeError("AuthenticationRejected")
                pending = {1, 2}
                for i, event_type in enumerate(("state_changed", "call_service"), start=1):
                    ws.send(json.dumps({"id": i, "type": "subscribe_events", "event_type": event_type}))
                while pending:
                    msg = json.loads(ws.recv())
                    if msg.get("type") == "result" and msg.get("id") in pending:
                        if not msg.get("success"):
                            raise RuntimeError("SubscriptionRejected")
                        pending.remove(msg["id"])
                    else:
                        handle_event(msg, entity, wake)
                ws.settimeout(None)
                print("Shopping sync HA event listener connected", flush=True)
                while True:
                    handle_event(json.loads(ws.recv()), entity, wake)
            finally:
                ws.close()
        except Exception as exc:
            category = type(exc).__name__
            if isinstance(exc, websocket.WebSocketBadStatusException):
                category += " HTTP " + str(exc.status_code)
            elif isinstance(exc, RuntimeError):
                category += " " + str(exc)
            print("Shopping sync HA event listener disconnected (" + category + "); retrying", flush=True)
            time.sleep(15)
