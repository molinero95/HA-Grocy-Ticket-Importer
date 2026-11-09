"""Manual Alexa decisions immediately become usable Grocy shopping rows."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

import shopping_match_queue as queue
from shopping_choice_conversion import manual_choice, remove_pending, delete_verified
from stock_commands import CommandConflict
import web


class ManualShoppingChoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "queue.sqlite3"
        env = patch.dict(os.environ, {"STOCK_COMMAND_DB": self.temp.name + "/commands.sqlite3"})
        env.start()
        self.addCleanup(env.stop)
        self.products = [{"id": 7, "name": "Arroz redondo", "qu_id_stock": 2},
                         {"id": 8, "name": "Arroz basmati", "qu_id_stock": 2}]
        self.rows = []
        self.writes = []
        self.next_id = 40
        queue.refresh(self.path, ["Arroz"], self.products)
        self.operation = str(uuid.uuid4())

    def grocy(self, method, endpoint, payload=None):
        if method == "GET":
            if endpoint == "objects/products":
                return copy.deepcopy(self.products)
            if endpoint == "objects/quantity_units":
                return [{"id": 2, "name": "Piece"}]
            if endpoint == "objects/shopping_list":
                return copy.deepcopy(self.rows)
            if endpoint.startswith("objects/shopping_list/"):
                return copy.deepcopy(next(row for row in self.rows if row["id"] == int(endpoint.split("/")[-1])))
            raise AssertionError(endpoint)
        # These decisions must never modify stock, products or another Grocy API.
        self.assertTrue(endpoint.startswith("objects/shopping_list"), endpoint)
        self.writes.append((method, endpoint, copy.deepcopy(payload)))
        if method == "POST":
            self.next_id += 1
            self.rows.append({"id": self.next_id, "product_id": None, "qu_id": None,
                              "done": 0, **payload})
            return {"created_object_id": self.next_id}
        target = int(endpoint.split("/")[-1])
        if method == "PUT":
            next(row for row in self.rows if row["id"] == target).update(payload)
        elif method == "DELETE":
            self.rows[:] = [row for row in self.rows if row["id"] != target]
        else:
            raise AssertionError(method)
        return {}

    def note(self, **changes):
        row = {"id": 1, "product_id": None, "amount": 2, "note": "Arroz", "qu_id": None,
               "done": "0", "shopping_list_id": 1, **changes}
        self.rows.append(row)
        return row

    def choose(self, product_id=8, operation=None):
        return manual_choice(self.grocy, queue, self.path, "arroz", product_id, operation or self.operation)

    def full_catalog_choice(self, product_id=9, **changes):
        return {"expected_name": "Arroz", "generation": 1,
                "product_name": next(p["name"] for p in self.products if p["id"] == product_id), **changes}

    def test_full_catalog_choice_survives_worker_refresh_without_name_similarity(self):
        self.products.append({"id": 9, "name": "Leche Clau", "qu_id_stock": 2})
        original = copy.deepcopy(self.note(amount=3))
        choice = self.full_catalog_choice()
        self.assertNotIn(9, [p['id'] for p in queue.pending(self.path)[0]['candidates']])
        for _ in range(2):
            result = manual_choice(self.grocy, queue, self.path, "arroz", 9, self.operation, catalog_choice=choice)
            self.assertEqual(result['item_id'], original['id'])
        self.assertEqual(self.rows[0], {**original, 'product_id': 9, 'qu_id': 2})
        self.assertEqual(len(self.writes), 1)
        self.products[-1]['name'] = 'Leche Jaime'
        queue.refresh(self.path, ['Arroz'], self.products)
        self.assertFalse(queue.pending(self.path)[0]['selection_stale'])
        choices = queue.resolved_choices(self.path, ['Arroz'], self.products)
        self.assertTrue(choices['arroz']['trusted_manual'])
        result, _, _ = self.worker(False)
        self.assertEqual(result['next_baseline'], ['p:9'])
        self.assertEqual(len(self.writes), 1)
        queue.refresh(self.path, [], self.products)
        queue.refresh(self.path, ['Arroz'], self.products)
        entry = queue.pending(self.path)[0]
        self.assertEqual(entry['generation'], 2)
        self.assertIsNone(entry['manual_product_id'])
        self.assertIsNone(entry['selected_product_id'])

    def test_full_catalog_request_rejects_stale_deleted_archived_and_forged_choices(self):
        self.products.append({"id": 9, "name": "Leche Clau", "qu_id_stock": 2})
        valid = self.full_catalog_choice()
        for choice in [False, [], {}, {**valid, 'generation': True}, {**valid, 'generation': 2},
                       {**valid, 'expected_name': 'Otro'}, {**valid, 'product_name': 'Otro'}]:
            with self.subTest(choice=choice), self.assertRaises(ValueError):
                manual_choice(self.grocy, queue, self.path, 'arroz', 9, self.operation, catalog_choice=choice)
        with self.assertRaises(ValueError):
            self.choose(9)  # An ordinary suggestion cannot bypass ranking.
        for state in ['0', 'deleted']:
            if state == 'deleted': self.products.pop()
            else: self.products[-1]['active'] = state
            with self.assertRaises(ValueError):
                manual_choice(self.grocy, queue, self.path, 'arroz', 9, self.operation, catalog_choice=valid)
        self.assertEqual(self.writes, [])
        self.assertIsNone(queue.pending(self.path)[0]['manual_product_id'])

    def test_removed_full_catalog_product_becomes_stale_without_resetting_identity(self):
        self.products.append({"id": 9, "name": "Leche Clau", "qu_id_stock": 2})
        manual_choice(self.grocy, queue, self.path, 'arroz', 9, self.operation, catalog_choice=self.full_catalog_choice())
        self.products[-1]['active'] = '0'
        queue.refresh_catalog(self.path, self.products)
        self.assertTrue(queue.pending(self.path)[0]['selection_stale'])
        self.assertEqual(queue.resolved_choices(self.path, ['Arroz'], self.products), {})
        with self.assertRaisesRegex(ValueError, 'renewed review'):
            self.worker(False)
        self.assertEqual(len(self.writes), 1)

    def test_full_catalog_choice_preserves_duplicate_and_attached_row_guards(self):
        self.products.append({"id": 9, "name": "Leche Clau", "qu_id_stock": 2})
        self.note()
        self.note(id=2, product_id=9, note='', amount=6)
        with self.assertRaisesRegex(ValueError, 'ya está en la lista'):
            manual_choice(self.grocy, queue, self.path, 'arroz', 9, self.operation, catalog_choice=self.full_catalog_choice())
        self.assertEqual(self.writes, [])
        self.rows.pop()
        self.choose(8)
        before = copy.deepcopy(self.rows)
        with self.assertRaisesRegex(ValueError, 'ya está asociado'):
            manual_choice(self.grocy, queue, self.path, 'arroz', 9, str(uuid.uuid4()), catalog_choice=self.full_catalog_choice())
        self.assertEqual(self.rows, before)

    def test_full_catalog_api_requires_csrf_and_persists_explicit_choice(self):
        self.products.append({"id": 9, "name": "Leche Jaime", "qu_id_stock": 2})
        self.note()
        client, headers = self.api()
        payload = {'product_id': 9, 'operation_id': self.operation, 'catalog_choice': self.full_catalog_choice()}
        url = '/api/v1/alexa/matches/arroz/choose'
        self.assertEqual(client.post(url, json=payload).status_code, 403)
        self.assertEqual(self.writes, [])
        for _ in range(2):
            response = client.post(url, json=payload, headers=headers)
            self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.rows[0]['product_id'], 9)
        self.assertEqual(len(self.writes), 1)

    def test_new_candidate_can_be_selected_without_waiting_for_worker_refresh(self):
        self.products.append({'id': 9, 'name': 'Arroz integral', 'qu_id_stock': 2})
        self.assertNotIn(9, [p['id'] for p in queue.pending(self.path)[0]['candidates']])
        self.note(amount=3)
        self.choose(9)
        self.assertEqual(self.rows[0]['product_id'], 9)
        self.assertEqual(self.rows[0]['amount'], 3)
        self.assertEqual([write[0] for write in self.writes], ['PUT'])

    def test_changed_candidates_cannot_create_a_second_row_for_an_already_associated_item(self):
        self.choose(8)
        self.products[1]['name'] = 'Pan'
        self.products.append({'id': 9, 'name': 'Arroz integral', 'qu_id_stock': 2})
        before = list(self.writes)
        with self.assertRaisesRegex(ValueError, 'ya está asociado'):
            self.choose(9, str(uuid.uuid4()))
        self.assertEqual(self.writes, before)
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(self.rows[0]['product_id'], 8)

    def test_archived_candidate_is_rejected_before_any_write(self):
        self.products[1]['active'] = '0'
        with self.assertRaises(ValueError):
            self.choose(8)
        self.assertEqual(self.writes, [])
        self.assertNotIn(8, [p['id'] for p in queue.pending(self.path)[0]['candidates']])

    def test_choice_creates_a_manageable_row_without_waiting_for_worker(self):
        result = self.choose()
        self.assertEqual(result["item_id"], self.rows[0]["id"])
        self.assertEqual(self.rows[0]["product_id"], 8)
        self.assertEqual(self.rows[0]["amount"], 1)
        entry = queue.pending(self.path)[0]
        self.assertTrue(entry["dismissed"])
        self.assertEqual(entry["shopping_entry_id"], result["item_id"])

    def test_existing_note_keeps_its_id_amount_note_and_other_rows(self):
        self.note()
        other = copy.deepcopy(self.note(id=2, shopping_list_id=2, amount=9))
        completed = copy.deepcopy(self.note(id=3, done="1"))
        result = self.choose()
        self.assertEqual(result["item_id"], 1)
        self.assertEqual(self.rows[0], {"id": 1, "product_id": 8, "amount": 2, "note": "Arroz",
                                      "qu_id": 2, "done": "0", "shopping_list_id": 1})
        self.assertEqual(self.rows[1:], [other, completed])
        self.assertEqual([w[0] for w in self.writes], ["PUT"])

    def test_repeated_save_does_not_add_quantity_or_duplicate_rows(self):
        first = self.choose()
        self.assertEqual(self.choose(), first)
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(len(self.writes), 1)

    def test_legacy_call_without_operation_id_is_also_idempotent(self):
        for _ in range(2):
            manual_choice(self.grocy, queue, self.path, "arroz", 8)
        self.assertEqual(len(self.writes), 1)

    def test_lost_write_response_is_never_replayed(self):
        def lost(method, endpoint, payload=None):
            result = self.grocy(method, endpoint, payload)
            if method == "POST":
                raise ConnectionError("Response lost after acceptance")
            return result
        with self.assertRaises(ConnectionError):
            manual_choice(lost, queue, self.path, "arroz", 8, self.operation)
        with self.assertRaises(CommandConflict):
            self.choose()
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(len(self.writes), 1)
        # A deliberate new decision reads the existing row; it never increments it.
        self.choose(operation=str(uuid.uuid4()))
        self.assertEqual(len(self.writes), 1)

    def test_existing_product_is_reused_without_increment(self):
        row = copy.deepcopy(self.note(product_id=8, note="", qu_id=2, amount=4))
        self.assertEqual(self.choose()["item_id"], row["id"])
        self.assertEqual(self.rows, [row])
        self.assertEqual(self.writes, [])

    def test_collision_with_existing_product_keeps_note_and_quantities(self):
        self.note()
        self.note(id=2, product_id=8, amount=5)
        before = copy.deepcopy(self.rows)
        with self.assertRaisesRegex(ValueError, "ya está en la lista"):
            self.choose()
        self.assertEqual(self.rows, before)
        self.assertEqual(self.writes, [])

    def test_preflight_conflict_allows_a_different_valid_choice(self):
        self.note()
        self.note(id=2, product_id=8, amount=5)
        with self.assertRaises(ValueError):
            self.choose(8)
        self.choose(7)
        self.assertEqual(self.rows[0]['product_id'], 7)
        self.assertEqual(self.rows[0]['amount'], 2)
        self.assertEqual(self.rows[1]['amount'], 5)

    def test_stale_or_archived_candidate_never_writes(self):
        self.products[1]["active"] = False
        with self.assertRaisesRegex(ValueError, "sugerencia ha cambiado"):
            self.choose()
        self.assertEqual(self.writes, [])

    def test_keep_original_creates_a_real_note_that_can_be_marked_or_removed(self):
        result = self.choose(0)
        self.assertEqual(self.rows[0]["note"], "Arroz")
        self.assertIsNone(self.rows[0]["product_id"])
        self.assertEqual(queue.pending(self.path)[0]["shopping_entry_id"], result["item_id"])
        self.assertEqual(self.choose(0), result)
        self.assertEqual(len(self.writes), 1)

    def test_remove_is_available_before_choosing_and_survives_queue_refresh(self):
        remove_pending(self.grocy, queue, self.path, "arroz")
        queue.refresh(self.path, ["Arroz"], self.products)
        self.assertTrue(queue.pending(self.path)[0]["removed"])
        with self.assertRaises(ValueError):
            self.choose()
        self.assertEqual(self.writes, [])

    def test_pending_removal_deletes_only_its_default_list_note(self):
        self.note()
        other = copy.deepcopy(self.note(id=2, shopping_list_id=2))
        remove_pending(self.grocy, queue, self.path, "arroz")
        self.assertEqual(self.rows, [other])
        self.assertTrue(queue.pending(self.path)[0]["removed"])
        self.assertEqual([w[0] for w in self.writes], ["DELETE"])

    def test_concurrent_note_change_blocks_deletion(self):
        original = copy.deepcopy(self.note())
        self.rows[0]["amount"] = 5
        with self.assertRaisesRegex(ValueError, "ha cambiado"):
            delete_verified(self.grocy, original)
        self.assertEqual(self.writes, [])

    def test_new_source_episode_clears_old_removal_and_command_identity(self):
        self.choose(0)
        remove_pending(self.grocy, queue, self.path, "arroz")
        queue.refresh(self.path, [], self.products)
        queue.refresh(self.path, ["Arroz"], self.products)
        entry = queue.pending(self.path)[0]
        self.assertFalse(entry["removed"])
        self.assertEqual(entry["generation"], 2)
        self.assertIsNone(entry["shopping_entry_id"])
        manual_choice(self.grocy, queue, self.path, "arroz", 8)
        self.assertEqual(self.rows[0]["product_id"], 8)

    def api(self):
        secret = patch.dict(web.app.config, {"SECRET_KEY": "manual-shopping-test-secret"})
        secret.start()
        self.addCleanup(secret.stop)
        context = patch.multiple(web, INGRESS_MODE=True)
        context.start()
        self.addCleanup(context.stop)
        for obj, attr, value in [(web.shopping_match_queue, "DEFAULT_PATH", self.path),
                                 (web.barcode_stock, "grocy", self.grocy)]:
            patcher = patch.object(obj, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        client = web.app.test_client()
        headers = {"X-CSRF-Token": client.get("/api/v1/auth/status").json["csrf_token"]}
        return client, headers

    def test_force_sync_is_csrf_protected_enabled_only_and_never_replays_same_operation(self):
        import shopping_sync_worker as worker
        client, headers = self.api()
        url = '/api/v1/shopping/sync'
        body = {'operation_id': self.operation}
        with patch.dict(os.environ, {'SHOPPING_SYNC_ENABLED': '1', 'ALEXA_SHOPPING_LIST_ENTITY': 'todo.test'}), \
             patch.object(worker, 'run_once', return_value={}) as run:
            self.assertEqual(client.post(url, json=body).status_code, 403)
            run.assert_not_called()
            for _ in range(2):
                result = client.post(url, json=body, headers=headers)
                self.assertEqual(result.status_code, 200, result.json)
            run.assert_called_once_with(dry_run=False, blocking=False)
            with patch.dict(os.environ, {'SHOPPING_SYNC_ENABLED': '0'}):
                self.assertEqual(client.post(url, json={'operation_id': str(uuid.uuid4())}, headers=headers).status_code, 409)
            self.assertEqual(run.call_count, 1)

    def test_force_sync_worker_busy_and_failures_do_not_escape_or_replay(self):
        import shopping_sync_worker as worker
        client, headers = self.api()
        url = '/api/v1/shopping/sync'
        with patch.dict(os.environ, {'SHOPPING_SYNC_ENABLED': '1', 'ALEXA_SHOPPING_LIST_ENTITY': 'todo.test'}):
            for error, status in [(BlockingIOError(), 409), (RuntimeError('private secret'), 503)]:
                body = {'operation_id': str(uuid.uuid4())}
                with patch.object(worker, 'run_once', side_effect=error) as run:
                    for _ in range(2):
                        result = client.post(url, json=body, headers=headers)
                        self.assertEqual(result.status_code, status, result.json)
                        self.assertNotIn('private', str(result.json))
                    run.assert_called_once()

    def test_force_sync_cannot_acquire_workers_shared_lock_or_touch_checkpoint(self):
        import shopping_sync_worker as worker
        client, headers = self.api()
        with patch.dict(os.environ, {'SHOPPING_SYNC_ENABLED': '1', 'ALEXA_SHOPPING_LIST_ENTITY': 'todo.test'}), \
             patch.object(worker, 'MATCH_QUEUE', self.path), \
             patch.object(worker, '_run_once') as run, \
             patch.object(worker, 'save_identity_state') as save, queue.mutation_lock(self.path):
            result = client.post('/api/v1/shopping/sync', json={'operation_id': self.operation}, headers=headers)
            self.assertEqual(result.status_code, 409, result.json)
            run.assert_not_called(); save.assert_not_called()
        self.assertEqual(self.writes, [])

    def test_choice_and_pending_remove_require_csrf(self):
        client, _ = self.api()
        self.assertEqual(client.post("/api/v1/alexa/matches/arroz/choose", json={"product_id": 8}).status_code, 403)
        self.assertEqual(client.delete("/api/v1/alexa/matches/arroz").status_code, 403)
        self.assertEqual(self.writes, [])

    def test_api_removal_tracks_the_exact_selected_row(self):
        client, headers = self.api()
        result = client.post("/api/v1/alexa/matches/arroz/choose", json={"product_id": 8}, headers=headers)
        self.assertEqual(result.status_code, 200, result.json)
        row_id = result.json["item_id"]
        shopping = client.get("/api/v1/shopping").json
        self.assertEqual(shopping["items"][0]["product_id"], 8)
        self.assertEqual(shopping["pending_matches"], [])
        self.assertEqual(client.post(f"/api/v1/shopping/{row_id}/toggle", json={"done": True}, headers=headers).status_code, 200)
        self.assertTrue(client.get("/api/v1/shopping").json["items"][0]["done"])
        self.assertEqual(client.delete(f"/api/v1/shopping/{row_id}", headers=headers).status_code, 200)
        self.assertEqual(self.rows, [])
        self.assertTrue(queue.pending(self.path)[0]["removed"])

    def test_worker_lock_rejects_manual_save_without_waiting_or_writing(self):
        client, headers = self.api()
        with queue.mutation_lock(self.path):
            response = client.post("/api/v1/alexa/matches/arroz/choose", json={"product_id": 8}, headers=headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"], "operation_in_progress")
        self.assertEqual(self.writes, [])

    def test_api_cannot_remove_another_list_item_while_a_suggestion_is_pending(self):
        self.note(shopping_list_id=2)
        client, headers = self.api()
        self.assertEqual(client.delete('/api/v1/shopping/1', headers=headers).status_code, 400)
        self.assertFalse(queue.pending(self.path)[0]['removed'])
        self.assertEqual(self.writes, [])

    def test_old_source_removal_does_not_delete_a_later_same_name_episode(self):
        remove_pending(self.grocy, queue, self.path, 'arroz')
        _, source, _ = self.worker(False)
        self.assertEqual(source, [])
        queue.refresh(self.path, ['Arroz'], self.products)
        self.assertEqual(queue.pending(self.path)[0]['generation'], 2)
        self.assertFalse(queue.pending(self.path)[0]['removed'])

    def test_failed_alexa_removal_never_advances_the_checkpoint(self):
        import shopping_sync_worker as worker
        remove_pending(self.grocy, queue, self.path, 'arroz')
        with patch.object(worker, 'MATCH_QUEUE', self.path), \
             patch.object(worker, 'grocy_entries', return_value=[]), \
             patch.object(worker, 'grocy', self.grocy), \
             patch.object(worker, 'ha_todo_items', return_value=['Arroz']), \
             patch.object(worker, 'remove_alexa_identity'), \
             patch.object(worker, 'save_identity_state') as save:
            with self.assertRaisesRegex(RuntimeError, 'could not be verified'):
                worker.run_once(dry_run=False)
        save.assert_not_called()
        self.assertTrue(queue.pending(self.path)[0]['removed'])

    def test_exact_note_resolution_preserves_quantity_and_unblocks_both_sync_directions(self):
        import shopping_sync_worker as worker
        from shopping_sync_status import snapshot
        self.products += [{"id": 9, "name": "Huevos", "qu_id_stock": 2},
                          {"id": 10, "name": "Tomate", "qu_id_stock": 2}]
        self.note(note="Arroz redondo", amount=2.5)
        self.note(id=2, note="", product_id=10, qu_id=2, amount=4)
        source = ["Arroz redondo", "Huevos"]
        def rows():
            by_id = {p["id"]: p["name"] for p in self.products}
            return [(by_id.get(r.get("product_id"), r["note"]), copy.deepcopy(r)) for r in self.rows]
        def add_grocy(row):
            self.rows.append({"id": 3, "product_id": row["product_id"], "amount": 1,
                              "note": "", "done": 0, "qu_id": 2, "shopping_list_id": 1})
        with patch.dict(os.environ, {"ALEXA_SHOPPING_LIST_ENTITY": "todo.test", "SHOPPING_SYNC_ENABLED": "1"}), \
             patch.object(worker, "MATCH_QUEUE", self.path), \
             patch.object(worker, "STATE_V2", Path(self.temp.name) / "checkpoint.json"), \
             patch.object(worker, "ha_todo_items", side_effect=lambda: list(source)), \
             patch.object(worker, "grocy_entries", side_effect=rows), \
             patch.object(worker, "grocy", self.grocy), \
             patch.object(worker, "add_alexa", side_effect=source.append) as alexa_write, \
             patch.object(worker, "add_grocy_identity", side_effect=add_grocy) as grocy_write:
            with self.assertRaisesRegex(ValueError, "canonical product"):
                worker.run_once(dry_run=False)
            self.assertEqual(snapshot(self.path)["reason"], "note_conflict")
            self.assertEqual(self.writes, [])
            alexa_write.assert_not_called()
            grocy_write.assert_not_called()
            review = queue.pending(self.path)[0]
            self.assertTrue(review["requires_product"])
            self.assertEqual(review["candidates"][0]["id"], 7)
            manual_choice(self.grocy, queue, self.path, "arroz redondo", 7, self.operation)
            self.assertEqual(self.rows[0]["id"], 1)
            self.assertEqual(self.rows[0]["note"], "Arroz redondo")
            self.assertEqual(self.rows[0]["amount"], 2.5)
            result = worker.run_once(dry_run=False)
            self.assertEqual(result["next_baseline"], ["p:10", "p:7", "p:9"])
            self.assertEqual(snapshot(self.path)["state"], "ok")
            alexa_write.assert_called_once_with("Tomate")
            self.assertEqual(grocy_write.call_args.args[0]["product_id"], 9)
            self.assertEqual([w[0] for w in self.writes], ["PUT"])

    def test_exact_note_cannot_be_kept_as_unresolved_text_or_merged_with_existing_product(self):
        self.note(note="Arroz redondo")
        queue.refresh(self.path, ["Arroz redondo"], self.products, [("Arroz redondo", self.rows[0])])
        with self.assertRaisesRegex(ValueError, "Asocia"):
            manual_choice(self.grocy, queue, self.path, "arroz redondo", 0, self.operation)
        self.note(id=2, product_id=7, note="")
        with self.assertRaisesRegex(ValueError, "ya está en la lista"):
            manual_choice(self.grocy, queue, self.path, "arroz redondo", 7, self.operation)
        self.assertEqual(self.writes, [])

    def worker(self, dry_run):
        import shopping_sync_worker as worker
        source = ["Arroz"]
        names = {int(p["id"]): p["name"] for p in self.products}
        def rows():
            return [(names.get(int(r.get("product_id") or 0), r["note"]), copy.deepcopy(r))
                    for r in self.rows if int(r.get("shopping_list_id") or 1) == 1 and not int(r.get("done") or 0)]
        def remove(_):
            source.clear()
        with patch.object(worker, "MATCH_QUEUE", self.path), \
             patch.object(worker, "STATE_V2", Path(self.temp.name) / "checkpoint.json"), \
             patch.object(worker, "ha_todo_items", side_effect=lambda: list(source)), \
             patch.object(worker, "grocy_entries", side_effect=rows), \
             patch.object(worker, "grocy", self.grocy), \
             patch.object(worker, "remove_alexa_identity", side_effect=remove) as remove_alexa:
            result = worker.run_once(dry_run=dry_run)
            return result, source, remove_alexa.call_count

    def test_disabled_worker_does_not_reimport_or_write_alexa_after_manual_removal(self):
        remove_pending(self.grocy, queue, self.path, "arroz")
        result, source, writes = self.worker(True)
        self.assertEqual(result["add_grocy"], [])
        self.assertEqual(source, ["Arroz"])
        self.assertEqual(writes, 0)

    def test_enabled_worker_applies_removal_before_first_union(self):
        self.choose()
        original = copy.deepcopy(self.rows[0])
        queue.stage_entry_removal(self.path, original)
        delete_verified(self.grocy, original)
        result, source, writes = self.worker(False)
        self.assertEqual(self.rows, [])
        self.assertEqual(source, [])
        self.assertEqual(writes, 1)
        self.assertEqual(result["next_baseline"], [])


if __name__ == "__main__":
    unittest.main()
