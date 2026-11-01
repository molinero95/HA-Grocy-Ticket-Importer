"""Stock dispatch must survive retries, process restarts and uncertain writes."""
import os
import tempfile
import unittest
import uuid
from unittest.mock import Mock, patch
from stock_commands import execute_once, CommandConflict
import barcode_stock


class StockCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"STOCK_COMMAND_DB": self.temp.name + "/commands.sqlite3"})
        env.start()
        self.addCleanup(env.stop)
        self.key = str(uuid.uuid4())

    def test_completed_request_replays_without_another_stock_write(self):
        operation = Mock(return_value={"status": 200, "body": {"shopping_error": True}})
        result = execute_once(self.key, {"amount": "1"}, operation)
        replay = execute_once(self.key, {"amount": "1"}, operation)
        self.assertEqual(result, replay)
        operation.assert_called_once()

    def test_uncertain_write_survives_reopen_and_is_never_retried(self):
        operation = Mock(side_effect=ConnectionError("Lost after Grocy accepted the request"))
        with self.assertRaises(ConnectionError):
            execute_once(self.key, {}, operation)
        with self.assertRaisesRegex(CommandConflict, "Resultado incierto"):
            execute_once(self.key, {}, operation)
        operation.assert_called_once()

    def test_same_key_cannot_be_used_with_a_different_quantity(self):
        operation = Mock(return_value={"status": 200})
        execute_once(self.key, {"amount": "1"}, operation)
        with self.assertRaises(CommandConflict):
            execute_once(self.key, {"amount": "2"}, operation)
        operation.assert_called_once()

    @patch("barcode_stock.grocy")
    def test_stale_stock_does_not_consume_or_replenish(self, grocy):
        grocy.side_effect = [{"id": 7, "name": "Leche"}, {"stock_amount": "2"}]
        with self.assertRaisesRegex(barcode_stock.BarcodeError, "ha cambiado"):
            barcode_stock.consume_product_quantity(7, "1", "3", True)
        self.assertTrue(all(call.args[0] == "GET" for call in grocy.call_args_list))

    @patch("barcode_stock.grocy")
    def test_refill_failure_returns_consumed_partial_result_without_retry(self, grocy):
        grocy.side_effect = [{"id": 7, "name": "Leche"}, {"stock_amount": "2"}, {}, ConnectionError()]
        result = barcode_stock.consume_product_quantity(7, "1", "2", True)
        self.assertTrue(result["shopping_error"])
        self.assertFalse(result["shopping_added"])
        self.assertEqual([call.args[1] for call in grocy.call_args_list if call.args[0] == "POST"], ["stock/products/7/consume"])
