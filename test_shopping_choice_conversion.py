"""Explicit Alexa choices preserve row IDs, quantities, notes and checkpoints."""
import unittest
from unittest.mock import Mock
from shopping_choice_conversion import project_choices, apply_choices
from shopping_identity_sync import IdentityConflict


class ChoiceConversionTests(unittest.TestCase):
    def setUp(self):
        self.original={'id':1,'product_id':None,'amount':2,'note':'Arroz','qu_id':None,'done':0,'shopping_list_id':1}
        self.products=[{'id':7,'name':'Arroz basmati','qu_id_stock':2}]
        self.choices={'arroz':{'product_id':7}}

    def test_projection_is_pure_and_preserves_original(self):
        rows,ops=project_choices([('Arroz',self.original)],self.products,self.choices)
        self.assertEqual(rows[0][1]['amount'],2)
        self.assertEqual(rows[0][1]['note'],'Arroz')
        self.assertIsNone(self.original['product_id'])
        self.assertEqual(ops[0][1]['product_id'],7)

    def test_existing_canonical_entry_is_not_silently_combined(self):
        with self.assertRaises(IdentityConflict):
            project_choices([('Arroz',self.original),('Arroz basmati',{'id':2,'product_id':7})],self.products,self.choices)

    def test_concurrent_note_edit_blocks_conversion_before_write(self):
        _,ops=project_choices([('Arroz',self.original)],self.products,self.choices)
        grocy=Mock(return_value={**self.original,'amount':3})
        with self.assertRaises(IdentityConflict):apply_choices(grocy,ops)
        grocy.assert_called_once_with('GET','objects/shopping_list/1')

    def test_apply_only_updates_the_explicitly_selected_identity(self):
        _,ops=project_choices([('Arroz',self.original)],self.products,self.choices)
        grocy=Mock(side_effect=[self.original,{},ops[0][1]])
        apply_choices(grocy,ops)
        grocy.assert_any_call('PUT','objects/shopping_list/1',{'product_id':7,'qu_id':2})
        self.assertFalse(any(call.args[0] in ('DELETE','POST') for call in grocy.call_args_list))
