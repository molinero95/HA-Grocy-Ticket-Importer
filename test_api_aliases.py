"""Alias management authentication, stale-delete and catalog failure guards."""
import tempfile
import os
from pathlib import Path
import unittest
from unittest.mock import patch
with patch.dict(os.environ, {"WEB_PASSWORD": "test-password", "WEB_SESSION_SECRET": "test-secret-key"}):
    import web
import api_aliases
from shopping_aliases import set_alias, list_aliases, choices

class AliasApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'aliases.sqlite3'
        for p in [patch.object(api_aliases, 'DEFAULT_PATH', self.path), patch.object(web, 'INGRESS_MODE', True),
                  patch.dict(web.app.config, SECRET_KEY='alias-test-session'),
                  patch.dict(os.environ, WEB_PASSWORD='test-password')]:
            p.start(); self.addCleanup(p.stop)
        self.client=web.app.test_client()
        self.headers={'X-CSRF-Token': self.client.get('/api/v1/auth/status').json['csrf_token']}

    def test_auth_and_csrf_precede_all_alias_mutations(self):
        with patch.object(web, 'INGRESS_MODE', False):
            self.assertEqual(self.client.get('/api/v1/alexa/aliases').status_code, 401)
        self.assertEqual(self.client.post('/api/v1/alexa/aliases',json={'name':'Leche','product_id':7}).status_code,403)
        self.assertEqual(self.client.delete('/api/v1/alexa/aliases/leche',json={'product_id':7}).status_code,403)
        self.assertEqual(self.client.put('/api/v1/alexa/aliases/leche',json={}).status_code,403)
        self.assertEqual(list_aliases(self.path), [])

    def test_catalog_outage_and_invalid_payloads_return_json_without_writes(self):
        for payload in [['bad'], {'name':'Leche','product_id':True}]:
            self.assertEqual(self.client.post('/api/v1/alexa/aliases',json=payload,headers=self.headers).status_code,400)
        with patch.object(api_aliases,'grocy',side_effect=ConnectionError('private')):
            response=self.client.post('/api/v1/alexa/aliases',json={'name':'Leche','product_id':7},headers=self.headers)
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private',response.get_data(as_text=True))
        self.assertEqual(list_aliases(self.path), [])

    def test_archived_targets_are_rejected_and_multiple_aliases_are_preserved(self):
        with patch.object(api_aliases,'grocy',return_value=[{'id':7,'active':'0'}]):
            self.assertEqual(self.client.post('/api/v1/alexa/aliases',json={'name':'Leche','product_id':7},headers=self.headers).status_code,404)
        with patch.object(api_aliases,'grocy',return_value=[{'id':7,'active':'1'}]):
            for name in ['Leche', 'Bebida blanca']:
                self.assertEqual(self.client.post('/api/v1/alexa/aliases',json={'name':name,'product_id':7},headers=self.headers).status_code,201)
        self.assertEqual(len(self.client.get('/api/v1/alexa/aliases').json['aliases']),2)

    def test_stale_delete_cannot_remove_an_alias_reassigned_to_another_product(self):
        set_alias(self.path,'Leche',8)
        response=self.client.delete('/api/v1/alexa/aliases/leche',json={'product_id':7},headers=self.headers)
        self.assertEqual(response.status_code,409)
        self.assertEqual(list_aliases(self.path)[0]['product_id'],8)
        self.assertEqual(self.client.delete('/api/v1/alexa/aliases/leche',json={'product_id':8},headers=self.headers).status_code,200)

    def test_inactive_alias_does_not_block_an_unrelated_sync(self):
        set_alias(self.path,'Leche',8)
        self.assertEqual(choices(self.path,[{'id':7}],names=['Tomate']),{})
        with self.assertRaises(ValueError):
            choices(self.path,[{'id':7}],names=['Leche'])

    def update(self, **changes):
        payload = dict(name='Leche normal', product_id=8, expected_name='Leche', expected_product_id=7)
        payload.update(changes)
        return self.client.put('/api/v1/alexa/aliases/leche', json=payload, headers=self.headers)

    def test_atomic_rename_and_reassignment_preserve_other_aliases(self):
        set_alias(self.path, 'Leche', 7); set_alias(self.path, 'Bebida blanca', 7)
        with patch.object(api_aliases, 'grocy', return_value=[{'id': 8, 'active': 1}]) as remote:
            response = self.update()
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['alias'], dict(key='leche normal', name='Leche normal', product_id=8))
        self.assertEqual({a['key']: a['product_id'] for a in list_aliases(self.path)}, {'leche normal': 8, 'bebida blanca': 7})
        remote.assert_called_once_with('GET', 'objects/products')

    def test_conflicting_destination_even_same_product_rolls_back_both_fields(self):
        set_alias(self.path, 'Leche', 7); set_alias(self.path, 'Leche normal', 8)
        before = list_aliases(self.path)
        with patch.object(api_aliases, 'grocy', return_value=[{'id': 8}]):
            self.assertEqual(self.update().status_code, 409)
        self.assertEqual(list_aliases(self.path), before)

    def test_stale_name_product_and_missing_source_never_overwrite(self):
        with patch.object(api_aliases, 'grocy', return_value=[{'id': 8}]):
            self.assertEqual(self.update().status_code, 409)
            set_alias(self.path, 'LECHE', 7)
            self.assertEqual(self.update().status_code, 409)
            self.assertEqual(self.update(expected_name='LECHE', expected_product_id=99).status_code, 409)
        self.assertEqual(list_aliases(self.path), [dict(key='leche', name='LECHE', product_id=7)])

    def test_edit_rejects_invalid_archived_targets_and_catalog_outage_without_writes(self):
        set_alias(self.path, 'Leche', 7)
        before = list_aliases(self.path)
        for patch_payload in ({'product_id': True}, {'expected_product_id': True}, {'name': ' '}, {'expected_name': []}):
            self.assertEqual(self.update(**patch_payload).status_code, 400)
        with patch.object(api_aliases, 'grocy', return_value=[{'id': 8, 'active': 0}]):
            self.assertEqual(self.update().status_code, 404)
        with patch.object(api_aliases, 'grocy', side_effect=ConnectionError('private')):
            response = self.update()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private', response.get_data(as_text=True))
        self.assertEqual(list_aliases(self.path), before)

    def test_selectable_names_come_from_cached_active_reviews_without_remote_reads(self):
        set_alias(self.path, 'Leche', 7)
        with patch('shopping_match_queue.pending', return_value=[{'name': 'Leche normal'}, {'name': 'Retirado', 'removed': True}]), patch.object(api_aliases, 'grocy') as remote:
            response = self.client.get('/api/v1/alexa/aliases')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['suggestions'], ['Leche normal'])
        remote.assert_not_called()
