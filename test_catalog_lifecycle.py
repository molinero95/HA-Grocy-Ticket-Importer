"""Reversible catalog lifecycle protects stock and Grocy's cascading history."""
import unittest
from unittest.mock import patch
import barcode_stock
from catalog_lifecycle import set_active


class LifecycleTests(unittest.TestCase):
    @patch('barcode_stock.grocy')
    def test_archive_never_deletes_history_or_consumes_stock(self, grocy):
        product={'id':7,'name':'Test','active':1}
        def call(method,path,body=None):
            if path=='objects/products/7':
                if method=='PUT':product.update(body); return {}
                return dict(product)
            if path=='stock/products/7':return {'stock_amount':0}
            return []
        grocy.side_effect=call
        self.assertFalse(set_active(7,'Test',False)['active'])
        self.assertEqual([c.args for c in grocy.call_args_list if c.args[0]!='GET'],[('PUT','objects/products/7',{'active':0})])

    @patch('barcode_stock.grocy')
    def test_nonzero_unknown_and_nan_stock_cannot_be_archived(self, grocy):
        for value in ('1','NaN'):
            grocy.reset_mock();grocy.side_effect=[{'id':7,'name':'Test'},{'stock_amount':value}]
            with self.assertRaises(barcode_stock.BarcodeError):set_active(7,'Test',False)
            self.assertTrue(all(call.args[0]=='GET' for call in grocy.call_args_list))

    @patch('barcode_stock.grocy')
    def test_active_shopping_reference_cannot_be_hidden(self, grocy):
        grocy.side_effect=[{'id':7,'name':'Test'},{'stock_amount':0},[{'product_id':7,'amount':1}]]
        with self.assertRaisesRegex(barcode_stock.BarcodeError,'sigue en uso'):set_active(7,'Test',False)
        self.assertTrue(all(call.args[0]=='GET' for call in grocy.call_args_list))

    @patch('barcode_stock.grocy')
    def test_restoration_changes_only_the_active_flag(self, grocy):
        grocy.side_effect=[{'id':7,'name':'Test','active':0},{},{'id':7,'name':'Test','active':1}]
        self.assertTrue(set_active(7,'Test',True)['active'])
        grocy.assert_any_call('PUT','objects/products/7',{'active':1})

    @patch('barcode_stock.grocy')
    def test_renamed_product_requires_refresh(self, grocy):
        grocy.return_value={'id':7,'name':'Changed'}
        with self.assertRaises(barcode_stock.BarcodeError):set_active(7,'Test',False)
        grocy.assert_called_once_with('GET','objects/products/7')

    @patch('barcode_stock.grocy')
    def test_missing_stock_response_cannot_authorize_archive(self, grocy):
        grocy.side_effect=[{'id':7,'name':'Test'},{}]
        with self.assertRaises(KeyError):set_active(7,'Test',False)
        self.assertTrue(all(call.args[0]=='GET' for call in grocy.call_args_list))
