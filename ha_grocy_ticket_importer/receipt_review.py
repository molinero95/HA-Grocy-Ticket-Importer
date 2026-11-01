"""Reviewed receipt identities and merchant-scoped mappings in the existing ledger."""
import re
import sqlite3
import unicodedata
from contextlib import closing
from decimal import Decimal
from pathlib import Path


def key(value):
    value = unicodedata.normalize('NFKC', str(value)).casefold()
    return ' '.join(value.split())


def mappings(path, merchant):
    if not Path(path).is_file():
        return {}
    with closing(sqlite3.connect(path)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='receipt_product_mappings'").fetchone():
            return {}
        rows = db.execute('SELECT source_name, product_id, stock_unit, pieces_per_pack FROM receipt_product_mappings WHERE merchant=?', (key(merchant),)).fetchall()
    return {name: {'product_id': pid, 'stock_unit': unit, 'pieces_per_pack': factor} for name, pid, unit, factor in rows}


def remember(db, merchant, item, product_id):
    if item.get('remember_product') is not True or not str(merchant).strip():
        return
    db.execute('''CREATE TABLE IF NOT EXISTS receipt_product_mappings (
        merchant TEXT NOT NULL, source_name TEXT NOT NULL, product_id INTEGER NOT NULL,
        stock_unit TEXT NOT NULL, pieces_per_pack INTEGER NOT NULL,
        PRIMARY KEY(merchant, source_name))''')
    db.execute('INSERT OR REPLACE INTO receipt_product_mappings VALUES (?,?,?,?,?)',
               (key(merchant), key(item.get('original_name', item['name'])), int(product_id), item['stock_unit'], int(item.get('pieces_per_pack', 1))))


def validate_review(item):
    quantity = Decimal(str(item.get('purchase_units', item['quantity'])))
    factor = Decimal(str(item.get('pieces_per_pack', 1)))
    if not quantity.is_finite() or not 0 < quantity <= 1000000 or quantity != quantity.quantize(Decimal('.001')):
        raise ValueError('Invalid purchase quantity')
    if not factor.is_finite() or factor != factor.to_integral_value() or not 1 <= factor <= 1000:
        raise ValueError('Invalid pack conversion')
    if 'unit_confirmed' in item and type(item['unit_confirmed']) is not bool:
        raise ValueError('Invalid unit confirmation')
    unit = item.get('stock_unit')
    if unit not in (None, 'piece', 'kg'):
        raise ValueError('Invalid stock unit')
    if unit == 'piece' and quantity != quantity.to_integral_value():
        raise ValueError('Pieces require whole quantities')
    if unit == 'kg' and factor != 1:
        raise ValueError('Kilograms cannot be converted to pieces')
    mode = item.get('product_mode', 'auto')
    if mode not in ('auto', 'existing', 'new'):
        raise ValueError('Invalid product selection')
    if mode == 'existing' and (type(item.get('product_id')) is not int or item['product_id'] <= 0):
        raise ValueError('Select an existing product')
    if mode != 'existing' and item.get('product_id') is not None:
        raise ValueError('Unexpected product identity')
    if 'remember_product' in item and type(item['remember_product']) is not bool:
        raise ValueError('Invalid mapping preference')
    if item.get('remember_product') and (mode == 'auto' or unit is None):
        raise ValueError('An explicit product and unit are required to remember a mapping')
    return quantity, int(factor)


def has_review(output):
    return bool(re.search(r'^\[\d+\] (?:REVIEW|SKIP pending)\b', output, re.MULTILINE))
