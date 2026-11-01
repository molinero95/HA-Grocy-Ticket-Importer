"""React entrypoint, authentication, prefix and no-JavaScript fallback contracts."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

with patch.dict(os.environ, {"WEB_PASSWORD":"test-password", "WEB_SESSION_SECRET":"test-secret-key"}):
    import web


class WebEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        Path(self.directory.name, 'index.html').write_text('<!doctype html><html><head></head><body><div id="root"></div></body></html>')
        env = patch.dict(os.environ, {"WEB_PASSWORD":"test-password", "FRONTEND_DIST_DIR":self.directory.name})
        env.start(); self.addCleanup(env.stop)
        self.client = web.app.test_client()

    def test_root_and_preview_serve_the_same_react_app_without_grocy_reads(self):
        with patch.object(web, 'INGRESS_MODE', False), patch.object(web.barcode_stock, 'grocy') as grocy:
            root = self.client.get('/')
            preview = self.client.get('/react/')
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.data, preview.data)
        self.assertIn(b'<noscript>', root.data)
        self.assertIn(b'/basic', root.data)
        grocy.assert_not_called()

    def test_prefix_is_used_for_base_and_basic_link(self):
        with patch.object(web, 'INGRESS_MODE', True):
            response = self.client.get('/', headers={'X-Ingress-Path':'/api/hassio_ingress/sample'})
        self.assertIn(b'<base href="/api/hassio_ingress/sample/">', response.data)
        self.assertIn(b'href="/api/hassio_ingress/sample/basic"', response.data)

    def test_old_write_routes_are_removed_and_cannot_modify_grocy(self):
        with patch.object(web, 'INGRESS_MODE', True), patch.object(web.barcode_stock, 'grocy') as grocy:
            token = self.client.get('/api/v1/auth/status').json['csrf_token']
            for path in ('/barcode/add','/product/1/delete','/commit/'+'a'*32,'/product/1/edit-all'):
                response = self.client.post(path, data={'csrf':token})
                self.assertEqual(response.status_code, 404, path)
        grocy.assert_not_called()

    def test_basic_login_and_writes_require_csrf(self):
        with patch.object(web, 'INGRESS_MODE', False):
            self.assertEqual(self.client.post('/basic/login', data={'password':'test-password'}).status_code, 403)
            self.client.get('/api/v1/auth/status')
            self.assertEqual(self.client.post('/api/v1/auth/login', json={'password':'test-password'}, headers={'X-CSRF-Token':'ñ'}).status_code, 403)
            self.client.get('/basic')
            with self.client.session_transaction() as session: token = session['csrf']
            self.assertEqual(self.client.post('/basic/login', data={'password':'contraseña','csrf':token}).status_code, 401)
            response = self.client.post('/basic/login', data={'password':'test-password','csrf':token})
            self.assertEqual(response.status_code, 303)
            self.assertEqual(self.client.post('/basic/shopping/1', data={'direction':'plus'}).status_code, 403)

    def test_basic_fallback_escapes_names_and_preserves_safe_forms(self):
        row = {'id':1,'name':'<script>bad</script>','amount':'0','unit':'Piece','shopping_amount':'0','shopping_unit':'Piece','shopping_step':'1','shopping_can_subtract':False}
        with patch.object(web, 'INGRESS_MODE', True), patch.object(web.barcode_stock, 'inventory_with_shopping', return_value=[row]):
            response = self.client.get('/basic')
        self.assertIn(b'&lt;script&gt;',response.data)
        self.assertNotIn(b'<script>',response.data)
        self.assertIn(b'action="/basic/shopping/1"',response.data)

    def test_api_responses_are_private_and_non_sniffable(self):
        response = self.client.get('/api/v1/auth/status')
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
        self.assertIn("object-src 'none'", response.headers['Content-Security-Policy'])

    def test_configuration_failure_is_structured(self):
        with patch.object(web, 'INGRESS_MODE', False), patch.dict(os.environ, {'WEB_PASSWORD':''}):
            response = self.client.get('/api/v1/auth/status')
        self.assertEqual(response.status_code,503)
        self.assertTrue(response.is_json)
