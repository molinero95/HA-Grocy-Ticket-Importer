"""Shopping reads rank current catalog candidates without remote mutations."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import web
import shopping_match_queue as queue

class CatalogSuggestionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'queue.sqlite3'
        self.products=[{'id':1,'name':'Arroz redondo','active':'1'}]
        self.items=[{'id':5,'name':'Arroz','amount':2,'unit':'Piece','product_id':None,'done':False,'image_url':None}]
        self.remote=patch.object(web.barcode_stock,'grocy',side_effect=lambda *args:copy.deepcopy(self.products))
        self.grocy=self.remote.start();self.addCleanup(self.remote.stop)
        for p in [patch.object(web,'INGRESS_MODE',True),patch.dict(web.app.config,SECRET_KEY='catalog-review-test'),
                  patch.object(queue,'DEFAULT_PATH',self.path),
                  patch.object(web.barcode_stock,'shopping_list_snapshot',side_effect=lambda:copy.deepcopy(self.items))]:
            p.start();self.addCleanup(p.stop)
        self.client=web.app.test_client()

    def candidates(self):
        data=self.client.get('/api/v1/shopping').json
        self.assertFalse(data['pending_matches_error'])
        self.assertEqual(data['items'],self.items)
        return data['pending_matches']

    def test_new_names_renames_and_archives_are_reflected_without_worker(self):
        self.assertEqual([p['id'] for p in self.candidates()[0]['candidates']],[1])
        self.products.append({'id':2,'name':'Arroz integral','active':'1'})
        self.assertEqual({p['id'] for p in self.candidates()[0]['candidates']},{1,2})
        self.products[0]['name']='Pasta'
        self.assertEqual([p['id'] for p in self.candidates()[0]['candidates']],[2])
        self.products[1]['active']='0'
        self.assertEqual(self.candidates()[0]['candidates'],[])
        self.assertEqual(self.grocy.call_count,4)
        for call in self.grocy.call_args_list:
            self.assertEqual(call.args,('GET','objects/products'))

    def test_failed_catalog_read_retains_list_and_previous_review_metadata(self):
        self.candidates()
        before=queue.pending(self.path)
        self.grocy.side_effect=ConnectionError('disposable catalog unavailable')
        response=self.client.get('/api/v1/shopping')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['items'],self.items)
        self.assertTrue(response.json['pending_matches_error'])
        self.assertEqual(response.json['pending_matches'],[])
        self.assertEqual(queue.pending(self.path),before)
