"""Photo-only web search, public-network boundaries and explicit local saving."""
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image

import web_product_photos as photos
import test_api_photos as photo_api
web = photo_api.web


def picture():
    output = io.BytesIO()
    Image.new('RGB', (20, 30), 'green').save(output, format='JPEG')
    return output.getvalue()


class PublicPhotoTests(unittest.TestCase):
    def test_private_mixed_dns_and_unsafe_urls_never_open_a_socket(self):
        for value in ('http://example.com/x', 'https://user:pass@example.com/x', 'https://127.0.0.1/x',
                      'https://[::1]/x', 'https://example.com:8100/x', 'https://localhost/x'):
            with self.subTest(value=value), self.assertRaises(ValueError): photos.public_url(value)
        for ips in (['127.0.0.1'], ['169.254.169.254'], ['10.1.1.1'], ['::1'], ['224.0.0.1'], ['ff02::1'], ['8.8.8.8', '192.168.1.1']):
            with self.subTest(ips=ips), patch.object(photos.socket, 'getaddrinfo', return_value=[(0, 0, 0, '', (ip, 443)) for ip in ips]), \
                 patch.object(photos.socket, 'create_connection') as connect, self.assertRaises(ValueError):
                photos.fetch_public('https://product.example.com/a', 100, time.monotonic() + 10)
            connect.assert_not_called()

    def response(self, status=200, **headers):
        response = Mock(status=status)
        response.getheader.side_effect = lambda key, default=None: headers.get(key, default)
        response.read1.side_effect = [b'public bytes', b'']
        return response

    def test_tls_pins_the_verified_address_and_preserves_host_without_auth_or_proxy(self):
        response = self.response(**{'Content-Type': 'text/html'})
        with patch.object(photos, 'public_addresses', return_value=['8.8.8.8']) as dns, \
             patch.object(photos.socket, 'create_connection') as connect, \
             patch.object(photos.ssl, 'create_default_context') as tls, \
             patch.object(photos.http.client, 'HTTPSConnection') as connection:
            connection.return_value.getresponse.return_value = response
            result = photos.fetch_public('https://manufacturer.example.com/product', 100, time.monotonic() + 10)
        self.assertEqual(result[0], b'public bytes')
        dns.assert_called_once_with('manufacturer.example.com')
        self.assertEqual(connect.call_args.args[0], ('8.8.8.8', 443))
        self.assertEqual(tls.return_value.wrap_socket.call_args.kwargs['server_hostname'], 'manufacturer.example.com')
        headers = connection.return_value.request.call_args.kwargs['headers']
        self.assertEqual(headers['Host'], 'manufacturer.example.com')
        self.assertFalse({'Authorization', 'Cookie'} & set(headers))

    def test_redirect_to_a_private_target_and_oversized_responses_are_rejected(self):
        response = self.response(status=302, Location='https://internal.example.com/secret')
        with patch.object(photos.socket, 'getaddrinfo', side_effect=[[(0, 0, 0, '', ('8.8.8.8', 443))], [(0, 0, 0, '', ('192.168.1.1', 443))]]), \
             patch.object(photos.socket, 'create_connection') as connect, patch.object(photos.ssl, 'create_default_context'), \
             patch.object(photos.http.client, 'HTTPSConnection') as connection:
            connection.return_value.getresponse.return_value = response
            with self.assertRaises(ValueError): photos.fetch_public('https://public.example.com/a', 100, time.monotonic() + 10)
            self.assertEqual(connect.call_count, 1)
        response = self.response(**{'Content-Length': '101'})
        with patch.object(photos, 'public_addresses', return_value=['8.8.8.8']), patch.object(photos.socket, 'create_connection'), \
             patch.object(photos.ssl, 'create_default_context'), patch.object(photos.http.client, 'HTTPSConnection') as connection:
            connection.return_value.getresponse.return_value = response
            with self.assertRaises(ValueError): photos.fetch_public('https://public.example.com/a', 100, time.monotonic() + 10)
            response.read1.assert_not_called()

    def test_product_image_precedes_unrelated_share_image_and_is_sanitized(self):
        html = b'<meta property="og:image" content="/share.jpg"><img alt="Pack de Choco Flakes" src="/pack.png">'
        with patch.object(photos, 'fetch_public', side_effect=[(html, 'https://manufacturer.example.com/product', 'text/html'),
                                                             (picture(), 'https://manufacturer.example.com/pack.png', 'image/png')]) as fetch:
            raw, source = photos.source_photo('https://manufacturer.example.com/product', 'Chocoflakes', time.monotonic() + 20)
        self.assertEqual(fetch.call_args.args[0], 'https://manufacturer.example.com/pack.png')
        self.assertEqual(source, 'https://manufacturer.example.com/product')
        self.assertEqual(Image.open(io.BytesIO(raw)).format, 'JPEG')

    def test_paid_search_has_no_catalog_filter_or_code_requirement_and_never_uses_model_image_urls(self):
        result = {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'https://internal/image.jpg',
                  'annotations': [{'type': 'url_citation', 'url': 'https://manufacturer.example.com/product'}]}]}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'disposable', 'OPENAI_MODEL': 'gpt-4.1-mini'}), \
             patch.object(photos.product_recognition, '_search_response', return_value=result) as request, \
             patch.object(photos, 'source_photo', return_value=(picture(), 'https://manufacturer.example.com/product')) as fetch:
            found = photos.search('anti cucarachas')
        self.assertEqual(len(found), 1);request.assert_called_once()
        payload = json.loads(request.call_args.args[0].data)
        self.assertFalse(payload['store']);self.assertEqual(payload['max_tool_calls'], 1)
        self.assertNotIn('filters', payload['tools'][0]);self.assertEqual(payload['tools'][0]['type'], 'web_search_preview')
        self.assertEqual(fetch.call_args.args[0], 'https://manufacturer.example.com/product')
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'disposable'}), \
             patch.object(photos.product_recognition, '_search_response', return_value=result), \
             patch.object(photos, 'source_photo', side_effect=OSError('private diagnostic')):
            with self.assertRaises(photos.product_recognition.DiscoveryError) as error:
                photos.search('Chocoflakes')
            self.assertEqual(error.exception.code, 'photo_sources_unavailable')
            self.assertNotIn('private diagnostic', str(error.exception))

    def test_expired_other_session_and_modified_cached_images_cannot_be_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            identity, _ = photos.cache_photo(root, picture(), 'https://manufacturer.example.com/product', 'owner')
            for candidate, session in (('../7', 'owner'), (identity, 'someone-else')):
                with self.assertRaises(ValueError): photos.cached_photo(root, candidate, session)
            path = root / '.web-search' / (identity + '.jpg')
            os.utime(path, (time.time() - 1801, time.time() - 1801))
            with self.assertRaises(ValueError): photos.cached_photo(root, identity, 'owner')


class WebPhotoApiTests(unittest.TestCase):
    setUp = photo_api.PhotoApiTests.setUp

    def test_web_photo_requires_consent_previews_in_session_and_saves_only_after_selection(self):
        from api_photos import local_image_url
        payload = {'name': 'Producto', 'query': 'Chocoflakes Cuetara', 'product_id': 7, 'consent': True}
        with patch.object(web.barcode_stock, 'product_detail', return_value=self.product), \
             patch.object(photos, 'search', return_value=[(picture(), 'https://manufacturer.example.com/product')]) as search, \
             patch.object(web.barcode_stock, 'save_product_photo') as remote:
            self.assertEqual(self.client.post('/api/v1/photos/web', json=payload).status_code, 403)
            response = self.client.post('/api/v1/photos/web', json={**payload, 'consent': False}, headers=self.headers)
            self.assertEqual(response.status_code, 400);search.assert_not_called()
            response = self.client.post('/api/v1/photos/web', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.json)
            candidate = response.json['candidates'][0]
            self.assertEqual(candidate['barcode'], '');self.assertFalse(Path(self.temp.name, '7.jpg').exists())
            self.assertEqual(self.client.get('/' + candidate['image_url']).status_code, 200)
            other = web.app.test_client();other.get('/api/v1/auth/status')
            self.assertEqual(other.get('/' + candidate['image_url']).status_code, 404)
            saved = self.client.post('/api/v1/catalog/products/7/photo-discovery', json={'token': candidate['discovery_token']}, headers=self.headers)
            self.assertTrue(saved.json['saved'], saved.json)
            self.assertEqual(saved.json['image_url'], local_image_url(7))
            self.assertEqual(photos.saved_source(Path(self.temp.name), 7), 'https://manufacturer.example.com/product')
            self.assertEqual(self.client.post('/api/v1/catalog/products/7/photo-discovery', json={'token': candidate['discovery_token']}, headers=self.headers).status_code, 409)
            remote.assert_not_called()

    def test_existing_local_photo_is_preserved_until_explicit_replacement_with_backup(self):
        previous = Path(self.temp.name, '7.jpg');previous.write_bytes(picture())
        payload = {'name': 'Producto', 'query': 'anti cucarachas', 'product_id': 7, 'consent': True}
        with patch.object(web.barcode_stock, 'product_detail', return_value=self.product), \
             patch.object(photos, 'search', return_value=[(picture(), 'https://manufacturer.example.com/anti')]):
            candidate = self.client.post('/api/v1/photos/web', json=payload, headers=self.headers).json['candidates'][0]
            path = '/api/v1/catalog/products/7/photo-discovery'
            response = self.client.post(path, json={'token': candidate['discovery_token']}, headers=self.headers)
            self.assertTrue(response.json['preserved'])
            self.assertFalse(list(Path(self.temp.name).glob('7.previous-*')))
            response = self.client.post(path, json={'token': candidate['discovery_token'], 'replace': True}, headers=self.headers)
            self.assertTrue(response.json['saved'], response.json)
            self.assertEqual(len(list(Path(self.temp.name).glob('7.previous-*.jpg'))), 1)
