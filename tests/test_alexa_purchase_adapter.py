"""Contract tests: removing a purchased alias targets its Alexa UID, not Grocy's label."""
import unittest
from unittest.mock import patch

import shopping_sync_adapters as adapters


class AlexaPurchaseAdapterTests(unittest.TestCase):
    def test_alias_removal_uses_source_uid(self):
        active = [{"summary": "Leche", "uid": "alexa-123", "status": "needs_action"}]
        with patch.object(adapters, "ALEXA_LIST", "todo.alexa_shopping"), \
             patch.object(adapters, "alexa_items", return_value=active), \
             patch.object(adapters, "ha_service") as service:
            adapters.remove_alexa_identity({"name": "Leche", "key": "p:7"})
        service.assert_called_once_with(
            "remove_item", {"entity_id": "todo.alexa_shopping", "item": "alexa-123"})

    def test_missing_source_does_not_remove_another_item(self):
        active = [{"summary": "Leche sin lactosa", "uid": "other"}]
        with patch.object(adapters, "alexa_items", return_value=active), \
             patch.object(adapters, "ha_service") as service:
            adapters.remove_alexa_identity({"name": "Leche"})
        service.assert_not_called()

    def test_duplicate_source_names_fail_closed(self):
        active = [{"summary": "Leche", "uid": "one"}, {"summary": "LECHE", "uid": "two"}]
        with patch.object(adapters, "alexa_items", return_value=active), \
             patch.object(adapters, "ha_service") as service:
            with self.assertRaises(ValueError):
                adapters.remove_alexa_identity({"name": "Leche"})
        service.assert_not_called()


if __name__ == "__main__":
    unittest.main()
