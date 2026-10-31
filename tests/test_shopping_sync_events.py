"""Regression tests for Home Assistant shopping events."""
import importlib.util
from pathlib import Path
import threading
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("shopping_sync_events", Path(__file__).resolve().parents[1] / "shopping_sync_events.py")
events = importlib.util.module_from_spec(spec)
spec.loader.exec_module(events)


def test_direct_core_websocket_default():
    with patch.dict("os.environ", {"HA_URL": "http://supervisor/core"}, clear=True):
        assert events.websocket_url() == "ws://homeassistant:8123/api/websocket"


def test_explicit_websocket_url():
    with patch.dict("os.environ", {"HA_WS_URL": "https://example.test:8123"}, clear=True):
        assert events.websocket_url() == "wss://example.test:8123/api/websocket"


def test_unrelated_events_do_not_wake():
    wake = threading.Event()
    events.handle_event({"type": "event", "event": {"event_type": "state_changed", "data": {"entity_id": "todo.other"}}}, "todo.target", wake)
    assert not wake.is_set()


def test_target_state_change_wakes():
    wake = threading.Event()
    events.handle_event({"type": "event", "event": {"event_type": "state_changed", "data": {"entity_id": "todo.target"}}}, "todo.target", wake)
    assert wake.is_set()


def test_service_target_wakes_without_substring_false_positive():
    wake = threading.Event()
    events.handle_event({"type": "event", "event": {"event_type": "call_service", "data": {"domain": "todo", "service_data": {"entity_id": ["todo.target_extra"]}}}}, "todo.target", wake)
    assert not wake.is_set()
    events.handle_event({"type": "event", "event": {"event_type": "call_service", "data": {"domain": "todo", "target": {"entity_id": "todo.target"}}}}, "todo.target", wake)
    assert wake.is_set()
