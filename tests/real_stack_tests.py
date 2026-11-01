"""Contracts exercised against an unmodified Grocy 4.7.1 service."""
import io
import unittest
import uuid
from PIL import Image


class RealStackTests(unittest.TestCase):
    def setUp(self):
        self.client = self.web.app.test_client()
        self.token = self.client.get('/api/v1/auth/status').json['csrf_token']
        self.headers = {'X-CSRF-Token': self.token}

    def test_manual_selection_is_immediate_and_removable_without_sync(self):
        from unittest.mock import patch
        import shopping_match_queue
        products = self.instance.http('GET', 'objects/products')
        chosen = next(p for p in products if p['name'] == 'Arroz basmati')
        shopping_match_queue.refresh(shopping_match_queue.DEFAULT_PATH, ['Arroz', 'Pasta'], products)
        note = self.instance.http('POST', 'objects/shopping_list',
            {'shopping_list_id': 1, 'note': 'Arroz', 'amount': 2})['created_object_id']
        with patch('shopping_sync_adapters.ha_service', side_effect=AssertionError('Manual choice must not call Alexa')):
            body = {'product_id': int(chosen['id']), 'operation_id': str(uuid.uuid4())}
            for _ in range(2):
                response = self.client.post('/api/v1/alexa/matches/arroz/choose', json=body, headers=self.headers)
                self.assertEqual(response.status_code, 200, response.json)
                self.assertEqual(response.json['item_id'], int(note))
            row = self.instance.http('GET', f'objects/shopping_list/{note}')
            self.assertEqual(row['amount'], 2)
            self.assertEqual(row['note'], 'Arroz')
            self.assertEqual(int(row['product_id']), int(chosen['id']))
            for done in (True, False):
                self.assertEqual(self.client.post(f'/api/v1/shopping/{note}/toggle',
                    json={'done': done}, headers=self.headers).status_code, 200)
            self.assertEqual(self.client.delete(f'/api/v1/shopping/{note}', headers=self.headers).status_code, 200)
            self.assertFalse(any(int(r['id']) == int(note) for r in self.instance.http('GET', 'objects/shopping_list')))
            self.assertEqual(self.client.delete('/api/v1/alexa/matches/pasta', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/v1/shopping').json['pending_matches'], [])

    def test_exact_note_review_preserves_real_row_quantity_and_stock(self):
        import shopping_match_queue
        from shopping_choice_conversion import manual_choice
        from shopping_identity_sync import plan_identity, IdentityConflict
        from shopping_sync_adapters import grocy_entries
        products = self.instance.http('GET', 'objects/products')
        product = next(p for p in products if p['name'] == 'Leche de prueba')
        pid = int(product['id'])
        before = self.instance.http('GET', f'stock/products/{pid}')['stock_amount']
        rid = int(self.instance.http('POST', 'objects/shopping_list',
            {'shopping_list_id': 1, 'note': product['name'], 'amount': 2.5})['created_object_id'])
        rows = grocy_entries()
        shopping_match_queue.refresh(shopping_match_queue.DEFAULT_PATH, [product['name']], products, rows)
        review = next(row for row in shopping_match_queue.pending(shopping_match_queue.DEFAULT_PATH)
                      if row['name'] == product['name'])
        self.assertTrue(review['requires_product'])
        with self.assertRaises(IdentityConflict):
            plan_identity([product['name']], [(product['name'], self.instance.http('GET', f'objects/shopping_list/{rid}'))], products)
        result = manual_choice(self.instance.http, shopping_match_queue, shopping_match_queue.DEFAULT_PATH,
                               review['key'], pid, str(uuid.uuid4()))
        self.assertEqual(result['item_id'], rid)
        row = self.instance.http('GET', f'objects/shopping_list/{rid}')
        self.assertEqual(float(row['amount']), 2.5)
        self.assertEqual(row['note'], product['name'])
        self.assertEqual(int(row['product_id']), pid)
        plan = plan_identity([product['name']], [(product['name'], row)], products)
        self.assertEqual(plan['add_grocy'], [])
        self.assertEqual(plan['add_alexa'], [])
        self.assertEqual(self.instance.http('GET', f'stock/products/{pid}')['stock_amount'], before)
        self.instance.http('DELETE', f'objects/shopping_list/{rid}')
        shopping_match_queue.refresh(shopping_match_queue.DEFAULT_PATH, [], products)

    def test_new_catalog_product_refreshes_unmatched_note_without_worker(self):
        name = 'Jabon dinamico'
        rid = int(self.instance.http('POST', 'objects/shopping_list',
            {'shopping_list_id': 1, 'note': name, 'amount': 3})['created_object_id'])
        first = self.client.get('/api/v1/shopping').json
        self.assertFalse(any(row['name'] == name for row in first['pending_matches']))
        units = self.client.get('/api/v1/catalog/units').json['units']
        piece = next(row['id'] for row in units if row['name'] == 'Piece')
        response = self.client.post('/api/v1/catalog/products', json={'name': name, 'unit_id': piece}, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.json)
        pid = response.json['product_id']
        second = self.client.get('/api/v1/shopping').json
        review = next(row for row in second['pending_matches'] if row['name'] == name)
        self.assertEqual([p['id'] for p in review['candidates']], [pid])
        chosen = self.client.post('/api/v1/alexa/matches/'+review['key']+'/choose', json={'product_id': pid, 'operation_id': str(uuid.uuid4())}, headers=self.headers)
        self.assertEqual(chosen.status_code, 200, chosen.json)
        self.assertEqual(chosen.json['item_id'], rid)
        row = self.instance.http('GET', f'objects/shopping_list/{rid}')
        self.assertEqual(row['amount'], 3)
        self.assertEqual(row['note'], name)
        self.assertEqual(self.instance.http('GET', f'stock/products/{pid}')['stock_amount'], 0)
        self.instance.http('DELETE', f'objects/shopping_list/{rid}')

    def test_pack_stock_shopping_and_consumption(self):
        units = self.client.get('/api/v1/catalog/units').json['units']
        pack = next(u['id'] for u in units if u['name'] == 'Pack')
        response = self.client.post('/api/v1/catalog/products', json={'name':'Pack contract', 'barcode':'8412345678901', 'unit_id':pack, 'initial_stock':'2', 'pack_size':'5'}, headers=self.headers)
        if response.status_code != 201:
            print("Conversion rows:", self.instance.http('GET','objects/quantity_unit_conversions'))
            import traceback
            try:
                from purchase_units import purchase_factor
                pid = self.instance.http('GET','objects/products')[-1]['id']
                print("Factor:", purchase_factor(self.instance.http, pid, pack, 2))
            except Exception: traceback.print_exc()
        self.assertEqual(response.status_code, 201, response.json)
        pid = response.json['product_id']
        product = self.client.get(f'/api/v1/catalog/products/{pid}').json
        self.assertEqual(float(product['stock_amount']), 10)
        self.assertEqual(product['pack_size'], 5)
        step = self.client.post(f'/api/v1/shopping/products/{pid}/step', json={'direction':'plus'}, headers=self.headers)
        self.assertEqual(step.status_code, 200, step.json)
        shopping = self.client.get('/api/v1/shopping').json['items']
        self.assertTrue(any(row['product_id'] == pid and not row['done'] for row in shopping), shopping)
        body = {'amount':'1','expected_amount':'10','add_to_list':True,'operation_id':str(uuid.uuid4())}
        for _ in range(2):
            consumed = self.client.post(f'/api/v1/catalog/products/{pid}/consume', json=body, headers=self.headers)
            self.assertEqual(consumed.status_code, 200, consumed.json)
        self.assertEqual(float(self.client.get(f'/api/v1/catalog/products/{pid}').json['stock_amount']), 9)

    def test_receipt_real_import_and_repeat_upload(self):
        upload = self.client.post('/api/v1/receipts', data={'ticket':(io.BytesIO(b'disposable-ticket-fixture'), 'ticket.pdf')}, headers=self.headers)
        self.assertEqual(upload.status_code, 201, upload.json)
        rid = upload.json['receipt_id']
        preview = self.client.post(f'/api/v1/receipts/{rid}/preview', json={'items':[{'name':'Yogur de prueba','purchase_units':'2','pieces_per_pack':5}]}, headers=self.headers)
        self.assertEqual(preview.status_code, 200, preview.json)
        committed = self.client.post(f'/api/v1/receipts/{rid}/commit', headers=self.headers)
        self.assertEqual(committed.status_code, 200, committed.json)
        products = self.instance.http('GET','objects/products')
        pid = next(int(p['id']) for p in products if p['name']=='Yogur de prueba')
        self.assertEqual(self.instance.http('GET', f'stock/products/{pid}')['stock_amount'], 10)
        self.assertNotEqual(self.client.post(f'/api/v1/receipts/{rid}/commit', headers=self.headers).status_code, 200)

    def test_variant_photo_and_metadata_survive_restart(self):
        product = next(p for p in self.instance.http('GET','objects/products') if p['name']=='Leche de prueba')
        pid = product['id']
        saved = self.client.post(f'/api/v1/products/{pid}/variants', json={'name':'Leche supermercado','barcode':'12345678','supermarket':'Test','brand':'Test','units_per_purchase':'1'}, headers=self.headers)
        self.assertEqual(saved.status_code, 200, saved.json)
        image = io.BytesIO(); Image.new('RGB',(20,20),'red').save(image,'PNG'); image.seek(0)
        uploaded = self.client.post(f'/api/v1/catalog/products/{pid}/photo', data={'photo':(image,'photo.png')}, headers=self.headers)
        self.assertEqual(uploaded.status_code, 200, uploaded.json)
        url = uploaded.json['photo_url']
        self.instance.stop(); self.instance.start()
        self.assertEqual(self.client.get(f'/api/v1/products/{pid}/variants').json['variants'][0]['barcode'], '12345678')
        self.assertEqual(self.client.get(f'/api/v1/catalog/products/{pid}').json['image_url'], url)
        self.assertEqual(self.client.get('/'+url).status_code, 200)

    def test_shopping_changes_do_not_touch_other_lists_notes_or_completed_rows(self):
        import barcode_stock
        piece=next(u['id'] for u in self.instance.http('GET','objects/quantity_units') if u['name']=='Piece')
        pid=barcode_stock.create_catalog_product('Shopping guard',unit_id=piece)['product_id']
        lid=self.instance.http('POST','objects/shopping_lists',{'name':'Independent list'})['created_object_id']
        other=self.instance.http('POST','objects/shopping_list',{'product_id':pid,'shopping_list_id':lid,'amount':9,'qu_id':piece,'note':'Other'})['created_object_id']
        own=self.instance.http('POST','objects/shopping_list',{'product_id':pid,'shopping_list_id':1,'amount':2,'qu_id':piece,'note':'Preserve'})['created_object_id']
        barcode_stock.change_shopping_quantity(pid,'minus')
        self.assertEqual(self.instance.http('GET',f'objects/shopping_list/{other}')['amount'],9)
        current=self.instance.http('GET',f'objects/shopping_list/{own}')
        self.assertEqual(current['amount'],1)
        self.assertEqual(current['note'],'Preserve')
        self.instance.http('PUT',f'objects/shopping_list/{own}',{'done':1})
        barcode_stock.change_shopping_quantity(pid,'plus')
        self.assertEqual(self.instance.http('GET',f'objects/shopping_list/{own}')['done'],1)
        active=[row for row in self.instance.http('GET','objects/shopping_list') if row['product_id']==pid and row['shopping_list_id']==1 and not row['done']]
        self.assertEqual(len(active),1)
        self.assertEqual(active[0]['amount'],1)

    def test_purchase_edit_and_archive_restore_never_rewrite_stock_or_history(self):
        import barcode_stock
        units={u['name']:u['id'] for u in self.instance.http('GET','objects/quantity_units')}
        pid=barcode_stock.create_catalog_product('Purchase lifecycle',unit_id=units['Piece'],initial_stock='3')['product_id']
        config={'purchase_unit_id':units['Pack'],'factor':'4','expected':{'unit_id':units['Piece'],'purchase_unit_id':units['Piece'],'factor':1},'operation_id':str(uuid.uuid4())}
        response=self.client.post(f'/api/v1/catalog/products/{pid}/purchase',json=config,headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.instance.http('GET',f'stock/products/{pid}')['stock_amount'],3)
        archived=self.client.post(f'/api/v1/catalog/products/{pid}/active',json={'active':False,'expected_name':'Purchase lifecycle','operation_id':str(uuid.uuid4())},headers=self.headers)
        self.assertEqual(archived.status_code,409)
        body={'amount':'3','expected_amount':'3','add_to_list':False,'operation_id':str(uuid.uuid4())}
        self.assertEqual(self.client.post(f'/api/v1/catalog/products/{pid}/consume',json=body,headers=self.headers).status_code,200)
        history=[row for row in self.instance.http('GET','objects/stock_log') if row['product_id']==pid]
        self.assertGreater(len(history),0)
        for active in (False,True):
            result=self.client.post(f'/api/v1/catalog/products/{pid}/active',json={'active':active,'expected_name':'Purchase lifecycle','operation_id':str(uuid.uuid4())},headers=self.headers)
            self.assertEqual(result.status_code,200,result.json)
            self.assertEqual(self.client.get(f'/api/v1/catalog/products/{pid}').status_code,200)
        self.assertEqual(history,[row for row in self.instance.http('GET','objects/stock_log') if row['product_id']==pid])
