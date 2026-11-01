"""Committed local changes wake the worker without replaying remote operations."""
import os
import tempfile
import threading
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
with patch.dict(os.environ, {'WEB_PASSWORD':'test-password','WEB_SESSION_SECRET':'test-secret-key'}):
    import web
import shopping_sync_events as events

class LocalWakeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'queue.sqlite3'

    def test_scoped_local_change_wakes_listener_without_waiting_for_polling_interval(self):
        wake,stop,ready=threading.Event(),threading.Event(),threading.Event()
        revision=events._revision
        def read(path):
            value=revision(path);ready.set();return value
        with patch.dict(os.environ, {'ALEXA_SHOPPING_LIST_ENTITY':'todo.test'}), patch.object(events,'_revision',side_effect=read):
            thread=threading.Thread(target=events.listen_local,args=(wake,self.path,stop),kwargs={'poll_seconds':0.01},daemon=True)
            thread.start()
            try:
                self.assertTrue(ready.wait(2))
                self.assertTrue(events.notify_local(self.path.with_name('other.sqlite3')))
                self.assertFalse(wake.wait(0.05))
                self.assertTrue(events.notify_local(self.path))
                self.assertTrue(wake.wait(2))
            finally:
                stop.set();thread.join(2)
            self.assertFalse(thread.is_alive())

    def test_missing_configuration_and_marker_failure_are_nonfatal(self):
        with patch.dict(os.environ, {'ALEXA_SHOPPING_LIST_ENTITY':''}):
            self.assertFalse(events.notify_local(self.path))
        with patch.dict(os.environ, {'ALEXA_SHOPPING_LIST_ENTITY':'todo.test'}), patch.object(Path,'touch',side_effect=OSError()):
            self.assertFalse(events.notify_local(self.path))

    def test_only_committed_api_mutations_request_a_sync(self):
        with patch.object(web,'INGRESS_MODE',True), patch.object(events,'notify_local') as wake, \
             patch.object(web.barcode_stock,'update_shopping_list_item') as update:
            client=web.app.test_client()
            token=client.get('/api/v1/auth/status').json['csrf_token']
            self.assertEqual(client.post('/api/v1/shopping/7/toggle',json={'done':True}).status_code,403)
            wake.assert_not_called()
            self.assertEqual(client.post('/api/v1/shopping/7/toggle',json={'done':True},headers={'X-CSRF-Token':token}).status_code,200)
            wake.assert_called_once_with(web.shopping_match_queue.DEFAULT_PATH)
            update.assert_called_once_with(7,True)
            wake.reset_mock()
            self.assertEqual(client.post('/api/v1/shopping/7/toggle',json={'done':'invalid'},headers={'X-CSRF-Token':token}).status_code,400)
            wake.assert_not_called()

    def test_receipt_preview_and_reads_do_not_request_sync(self):
        with web.app.test_request_context('/api/v1/receipts/fixture/preview',method='POST'),patch.object(events,'notify_local') as wake:
            web.security_headers(web.app.response_class('{}',status=200))
            wake.assert_not_called()
        with web.app.test_request_context('/api/v1/shopping',method='GET'),patch.object(events,'notify_local') as wake:
            web.security_headers(web.app.response_class('{}',status=200))
            wake.assert_not_called()

    def test_quick_controls_do_not_race_an_active_worker(self):
        import shopping_match_queue as queue
        with patch.object(web,'INGRESS_MODE',True), patch.object(queue,'DEFAULT_PATH',self.path), \
             patch.object(events,'notify_local') as wake, patch.object(web.barcode_stock,'change_shopping_quantity') as change:
            client=web.app.test_client()
            token=client.get('/api/v1/auth/status').json['csrf_token']
            with queue.mutation_lock(self.path):
                response=client.post('/api/v1/shopping/products/7/step',json={'direction':'plus'},headers={'X-CSRF-Token':token})
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.json['error'],'operation_in_progress')
            change.assert_not_called()
            wake.assert_not_called()
