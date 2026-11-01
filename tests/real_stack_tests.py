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
        unmatched = next(row for row in first['pending_matches'] if row['name'] == name)
        self.assertEqual(unmatched['candidates'], [])
        units = self.client.get('/api/v1/catalog/units').json['units']
        piece = next(row['id'] for row in units if row['name'] == 'Piece')
        response = self.client.post('/api/v1/catalog/products', json={'name': name, 'unit_id': piece}, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.json)
        pid = response.json['product_id']
        second = self.client.get('/api/v1/shopping').json
        review = next(row for row in second['pending_matches'] if row['name'] == name)
        self.assertEqual(review['generation'], unmatched['generation'])
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

    def test_delete_unused_archive_only_and_preserve_unrelated_grocy_history(self):
        import barcode_stock
        units = {u['name']: u['id'] for u in self.instance.http('GET', 'objects/quantity_units')}
        before = {entity: self.instance.http('GET', 'objects/' + entity)
                  for entity in ('stock', 'stock_log', 'shopping_list')}
        pid = barcode_stock.create_catalog_product('Disposable archive', barcode='8419876543210',
                unit_id=units['Pack'], initial_stock='0', pack_size='5')['product_id']
        url = f'/api/v1/catalog/products/{pid}'
        result = self.client.post(url + '/active', json={'expected_name': 'Disposable archive', 'active': False,
                                  'operation_id': str(uuid.uuid4())}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.json)
        preview = self.client.get(url + '/deletion')
        self.assertEqual(preview.status_code, 200, preview.json)
        self.assertTrue(preview.json['allowed'], preview.json)
        self.assertEqual(preview.json['barcode_count'], 1)
        self.assertGreater(preview.json['conversion_count'], 0)
        payload = {'expected_name': 'Disposable archive', 'confirmation': 'Disposable archive',
                   'token': preview.json['token'], 'operation_id': str(uuid.uuid4())}
        for _ in range(2):
            response = self.client.delete(url, json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.json)
        for entity in ('products', 'product_barcodes', 'quantity_unit_conversions'):
            field = 'id' if entity == 'products' else 'product_id'
            self.assertFalse(any(str(row[field]) == str(pid) for row in self.instance.http('GET', 'objects/' + entity)))
        for entity, original in before.items():
            self.assertEqual(self.instance.http('GET', 'objects/' + entity), original)
        # Movement history can be deleted only after explicit acknowledgement.
        pid = barcode_stock.create_catalog_product('Historical archive', unit_id=units['Piece'], initial_stock='1')['product_id']
        barcode_stock.consume_product_quantity(pid, '1', '1', False)
        url = f'/api/v1/catalog/products/{pid}'
        response = self.client.post(url + '/active', json={'expected_name': 'Historical archive', 'active': False,
                                    'operation_id': str(uuid.uuid4())}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        history = self.instance.http('GET', 'objects/stock_log')
        preview = self.client.get(url + '/deletion')
        self.assertEqual(preview.status_code, 200, preview.json)
        self.assertTrue(preview.json['allowed'], preview.json)
        self.assertGreater(preview.json['history_count'], 0)
        payload = {'expected_name': 'Historical archive', 'confirmation': 'Historical archive',
                   'token': preview.json['token'], 'operation_id': str(uuid.uuid4())}
        response = self.client.delete(url, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 409, response.json)
        self.assertEqual(self.instance.http('GET', 'objects/stock_log'), history)
        payload.update(delete_history=True, operation_id=str(uuid.uuid4()))
        response = self.client.delete(url, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.instance.http('GET', 'objects/stock_log'), [row for row in history if row['product_id'] != pid])
        self.assertFalse(any(row['id'] == pid for row in self.instance.http('GET', 'objects/products')))

    def test_native_merge_preserves_real_lots_history_codes_and_reference_rows(self):
        import barcode_stock
        units = {u['name']: u['id'] for u in self.instance.http('GET', 'objects/quantity_units')}
        source = barcode_stock.create_catalog_product('Merge source contract', barcode='8411231231231', unit_id=units['Piece'], initial_stock='2')['product_id']
        target = barcode_stock.create_catalog_product('Merge target contract', barcode='8411231231232', unit_id=units['Piece'], initial_stock='3')['product_id']
        shopping_id = int(self.instance.http('POST', 'objects/shopping_list', {'shopping_list_id': 1, 'product_id': source, 'amount': 2.5, 'note': 'Preserve this note'})['created_object_id'])
        recipe = int(self.instance.http('POST', 'objects/recipes', {'name': 'Merge recipe contract'})['created_object_id'])
        self.instance.http('POST', 'objects/recipes_pos', {'recipe_id': recipe, 'product_id': source, 'amount': 1, 'qu_id': units['Piece']})
        self.instance.http('POST', 'objects/meal_plan', {'day': '2026-11-01', 'type': 'product', 'product_id': source, 'product_amount': 1})
        before = {entity: [row for row in self.instance.http('GET', 'objects/' + entity) if row.get('product_id') in (source, target)]
                  for entity in ('stock', 'stock_log', 'product_barcodes', 'shopping_list', 'recipes_pos', 'meal_plan')}
        self.assertGreater(len(before['stock_log']), 0)
        response = self.client.get(f'/api/v1/catalog/merge-preview?source_id={source}&target_id={target}')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json['can_merge'], response.json)
        payload = {'source_id': source, 'target_id': target, 'expected_source': 'Merge source contract', 'expected_target': 'Merge target contract', 'confirmation': 'Merge target contract', 'token': response.json['token'], 'operation_id': str(uuid.uuid4())}
        for _ in range(2):
            response = self.client.post('/api/v1/catalog/products/merge', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.json)
        self.assertFalse(any(p['id'] == source for p in self.instance.http('GET', 'objects/products')))
        self.assertEqual(float(self.instance.http('GET', f'stock/products/{target}')['stock_amount']), 5)
        for entity, rows in before.items():
            after = {row['id']: row for row in self.instance.http('GET', 'objects/' + entity)}
            for row in rows:
                if entity == 'recipes_pos' and int(row.get('recipe_id') or 0) < 0:
                    continue  # Grocy rebuilds derived day/week recipes; server verifies totals.
                actual = after[row['id']]
                self.assertEqual(actual['product_id'], target)
                for field in ('amount', 'price', 'stock_id', 'note', 'barcode', 'product_amount'):
                    if field in row: self.assertEqual(actual[field], row[field], (entity, field))
        self.instance.http('DELETE', f'objects/shopping_list/{shopping_id}')

    def test_stock_threshold_and_opt_out_never_write_grocy_stock_or_shopping(self):
        import barcode_stock
        units = {u['name']: u['id'] for u in self.instance.http('GET', 'objects/quantity_units')}
        pid = barcode_stock.create_catalog_product('Threshold contract', unit_id=units['Piece'], initial_stock='2')['product_id']
        before = {entity: self.instance.http('GET', 'objects/' + entity) for entity in ('products', 'stock', 'stock_log', 'shopping_list')}
        url = f'/api/v1/catalog/products/{pid}/stock-threshold'
        for enabled, expected_enabled, value, expected in [(True, True, '2', '0'), (False, True, '2', '2')]:
            result = self.client.put(url, json={'amount': value, 'expected': expected, 'warning_enabled': enabled, 'expected_warning_enabled': expected_enabled}, headers=self.headers)
            self.assertEqual(result.status_code, 200, result.json)
        product = self.client.get(f'/api/v1/catalog/products/{pid}').json
        self.assertEqual(product['stock_threshold'], '2')
        self.assertFalse(product['stock_warning_enabled'])
        self.instance.stop(); self.instance.start()
        product = self.client.get(f'/api/v1/catalog/products/{pid}').json
        self.assertEqual(product['stock_threshold'], '2')
        self.assertFalse(product['stock_warning_enabled'])
        for entity, rows in before.items(): self.assertEqual(self.instance.http('GET', 'objects/' + entity), rows)

    def test_create_from_unknown_alexa_preserves_real_note_and_stock_without_duplicates(self):
        import shopping_match_queue as queue
        units = {u['name']: u['id'] for u in self.instance.http('GET', 'objects/quantity_units')}
        for has_note in (True, False):
            name = 'Alexa unknown source ' + str(has_note)
            original = None
            if has_note:
                rid = self.instance.http('POST', 'objects/shopping_list', {'shopping_list_id': 1, 'note': name, 'amount': 2.5})['created_object_id']
                original = self.instance.http('GET', f'objects/shopping_list/{rid}')
            products = self.instance.http('GET', 'objects/products')
            queue.refresh(queue.DEFAULT_PATH, [name], products)
            row = next(row for row in queue.pending(queue.DEFAULT_PATH) if row['name'] == name)
            self.assertEqual(row['candidates'], [])
            before = {entity: self.instance.http('GET', 'objects/' + entity) for entity in ('stock', 'stock_log')}
            base = '/api/v1/alexa/matches/' + name + '/'
            context = self.client.get(base + 'create-context')
            self.assertEqual(context.status_code, 200, context.json)
            payload = {'expected_name': name, 'generation': context.json['generation'], 'operation_id': str(uuid.uuid4()),
                       'product': {'name': 'Jabon canonico creado ' + str(has_note), 'unit_id': units['Piece'], 'initial_stock': '0'}}
            for _ in range(2):
                result = self.client.post(base + 'create-product', json=payload, headers=self.headers)
                self.assertEqual(result.status_code, 201, result.json)
                self.assertTrue(result.json['associated'])
            pid = result.json['product_id']
            saved = self.instance.http('GET', f"objects/shopping_list/{result.json['item_id']}")
            self.assertEqual(saved['product_id'], pid)
            self.assertEqual(saved['note'], name)
            self.assertEqual(float(saved['amount']), 2.5 if has_note else 1)
            if original: self.assertEqual(saved['id'], original['id'])
            self.assertEqual(float(self.instance.http('GET', f'stock/products/{pid}')['stock_amount']), 0)
            for entity, rows in before.items(): self.assertEqual(self.instance.http('GET', 'objects/' + entity), rows)
            self.assertEqual(queue.resolved_choices(queue.DEFAULT_PATH, [name], self.instance.http('GET', 'objects/products'))[name.lower()]['product_id'], pid)
            self.instance.http('DELETE', f"objects/shopping_list/{saved['id']}")
