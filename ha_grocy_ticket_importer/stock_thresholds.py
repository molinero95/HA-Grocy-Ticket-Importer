"""Display-only stock thresholds in the existing persistent metadata catalog.

Never change Grocy min_stock_amount: that field may auto-add shopping rows.
"""
from contextlib import closing
from decimal import Decimal, InvalidOperation
from generic_catalog import connect
import variant_catalog


def _amount(value):
    try: amount = Decimal(str(value).strip().replace(',', '.'))
    except (InvalidOperation, ValueError): raise ValueError('Indica un umbral válido') from None
    if not amount.is_finite() or not 0 <= amount < 1000000 or amount.as_tuple().exponent < -2:
        raise ValueError('El umbral debe ser positivo o cero, con un máximo de dos decimales')
    return format(amount.normalize(), 'f')


def _connect():
    db = connect(variant_catalog.CATALOG_DB)
    db.execute('CREATE TABLE IF NOT EXISTS stock_thresholds (product_id INTEGER PRIMARY KEY CHECK(product_id > 0), amount TEXT NOT NULL)')
    db.execute('BEGIN IMMEDIATE')
    if 'warning_enabled' not in {row[1] for row in db.execute('PRAGMA table_info(stock_thresholds)')}:
        db.execute('ALTER TABLE stock_thresholds ADD COLUMN warning_enabled INTEGER NOT NULL DEFAULT 1 CHECK(warning_enabled IN (0,1))')
    db.commit()
    return db


def settings():
    with closing(_connect()) as db:
        return {int(pid): {'amount': _amount(value), 'warning_enabled': bool(enabled)} for pid, value, enabled in db.execute('SELECT product_id,amount,warning_enabled FROM stock_thresholds')}

def thresholds():
    return {pid: row['amount'] for pid, row in settings().items()}


def save_threshold(product_id, amount, expected, warning_enabled=True, expected_warning_enabled=True):
    if type(warning_enabled) is not bool or type(expected_warning_enabled) is not bool: raise ValueError('Indica si quieres avisos de stock')
    pid, amount, expected = int(product_id), _amount(amount), _amount(expected)
    if pid <= 0: raise ValueError('Producto no válido')
    with closing(_connect()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT amount,warning_enabled FROM stock_thresholds WHERE product_id=?', (pid,)).fetchone()
        current = _amount(row[0]) if row else '0'
        current_enabled = bool(row[1]) if row else True
        if current != expected or current_enabled != expected_warning_enabled:
            if current == amount and current_enabled == warning_enabled: return amount  # Repeating an already saved local value is harmless.
            raise ValueError('El umbral ha cambiado. Actualiza la ficha antes de guardar')
        db.execute('INSERT INTO stock_thresholds(product_id,amount,warning_enabled) VALUES(?,?,?) ON CONFLICT(product_id) DO UPDATE SET amount=excluded.amount,warning_enabled=excluded.warning_enabled', (pid, amount, int(warning_enabled)))
    return amount
