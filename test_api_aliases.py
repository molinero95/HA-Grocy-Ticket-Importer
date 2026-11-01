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
