"""Persistent explicit differences between pairs of canonical Grocy IDs."""
from contextlib import closing
from generic_catalog import connect
import variant_catalog


def _connect():
    db = connect(variant_catalog.CATALOG_DB)
    db.execute('''CREATE TABLE IF NOT EXISTS duplicate_differences (
        left_id INTEGER NOT NULL, right_id INTEGER NOT NULL,
        left_name TEXT NOT NULL, right_name TEXT NOT NULL,
        PRIMARY KEY(left_id, right_id), CHECK(left_id < right_id))''')
    db.commit()
    return db


def differences():
    with closing(_connect()) as db:
        return [{'left_id': left, 'right_id': right, 'left_name': a, 'right_name': b}
                for left, right, a, b in db.execute('SELECT * FROM duplicate_differences ORDER BY left_id,right_id')]


def set_different(left, right):
    if int(left['id']) == int(right['id']):
        raise ValueError('Selecciona dos productos distintos')
    a, b = sorted((left, right), key=lambda p: int(p['id']))
    with closing(_connect()) as db, db:
        db.execute('INSERT INTO duplicate_differences VALUES(?,?,?,?) ON CONFLICT(left_id,right_id) DO NOTHING',
                   (int(a['id']), int(b['id']), a['name'], b['name']))


def undo_difference(left_id, right_id):
    a, b = sorted((int(left_id), int(right_id)))
    with closing(_connect()) as db, db:
        db.execute('DELETE FROM duplicate_differences WHERE left_id=? AND right_id=?', (a, b))
