#!/usr/bin/env python3
"""Grocy ticket importer v4: cautious auto-creation with review and dry-run.
Run from its directory; environment variables GROCY_URL/GROCY_API_KEY required.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DB_PATH = os.environ.get('GROCY_IMPORT_DB', str(Path(__file__).resolve().parent / 'grocy_imports.sqlite3'))

class GrocyError(Exception):
    pass

def grocy(method, path, body=None):
    base = os.environ['GROCY_URL'].rstrip('/')
    headers = {'GROCY-API-KEY': os.environ['GROCY_API_KEY'], 'Accept': 'application/json'}
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    request = urllib.request.Request(base + '/api/' + path, headers=headers, data=data, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raise GrocyError(f'HTTP {exc.code} {path}: {exc.read(300).decode(errors="replace")}') from exc

def norm(value):
    value = unicodedata.normalize('NFKD', value.casefold())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())

def dec(value):
    return Decimal(str(value))

def money(value):
    return dec(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

def classify(item):
    name = norm(item['name'])
    qty = dec(item['quantity'])
    if item.get('ambiguous'):
        return 'REVIEW', None, item.get('reason') or 'AI marked ambiguous'
    if any(x in name for x in ('gastos servicio', 'gastos envio', 'servicio domicilio', 'bolsa reutilizable', 'bolsa compra')):
        return 'EXPENSE', None, 'Non-stock charge (tracked in local expense ledger)'
    if re.search(r'\bhielo\b', name) and re.search(r'\bbolsa\b', name) and qty == 1:
        return 'STOCK', 2, ''
    # Packed bags with an explicit weight represent one purchased unit.
    if qty == 1 and re.search(r'\bbolsa\s+\d+(?:\s+\d+)?\s+kg$', name):
        return 'STOCK', 2, ''
    # Weighted fish may include a parenthesized size range: lubina kg (800-1200 g).
    if qty != qty.to_integral_value() and re.search(r'\bkg\s+\d+\s+\d+\s+g$', name):
        return 'STOCK', 4, ''
    # A trailing 'kg' plus a fractional quantity indicates a weighed line.
    # Packaged goods such as 'hielo bolsa 2 kg' have qty=1 and stay as Piece.
    weighed = bool(re.search(r'\bkg\s*$', name)) and qty != qty.to_integral_value()
    if weighed:
        return 'STOCK', 4, ''
    if qty != qty.to_integral_value():
        return 'REVIEW', None, 'Fractional quantity without reliable weight unit'
    if re.search(r'\bkg\s*$', name) and qty == qty.to_integral_value():
        return 'REVIEW', None, 'Whole-kg line: could be weighed or packaged'
    return 'STOCK', 2, ''

def validate(receipt):
    dt.date.fromisoformat(receipt['receipt_date'])
    if not receipt.get('items'):
        raise ValueError('No items')
    total = Decimal('0')
    for item in receipt['items']:
        factor = dec(item.get('pieces_per_pack', 1))
        purchased = dec(item.get('purchase_units', item['quantity']))
        if (not factor.is_finite() or factor != factor.to_integral_value()
                or not 1 <= factor <= 1000 or not purchased.is_finite()
                or purchased != dec(item['quantity'])):
            raise ValueError('Invalid pack conversion or purchase quantity')
        if not isinstance(item.get('name'), str) or not item['name'].strip():
            raise ValueError('Missing name')
        qty, price = dec(item['quantity']), dec(item['unit_price'])
        if qty <= 0 or price < 0:
            raise ValueError('Invalid quantity or price')
        total += money(qty * price)
    if money(total) != money(receipt['total']):
        raise ValueError(f'Total mismatch: calculated {money(total)}, ticket {money(receipt["total"])}')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--commit', action='store_true')
    args = parser.parse_args()
    # Read secrets from local .env without printing or exporting them.
    from dotenv import load_dotenv
    load_dotenv(os.environ.get('GROCY_ENV_FILE', str(Path(__file__).resolve().parent / '.env')))
    receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
    validate(receipt)
    digest = receipt.get('source_sha256') or hashlib.sha256(args.receipt.read_bytes()).hexdigest()
    products = grocy('GET', 'objects/products')
    units = {int(u['id']): u['name'] for u in grocy('GET', 'objects/quantity_units')}
    if 2 not in units or 4 not in units:
        raise ValueError('Expected Piece=2 and Kilogram=4; verify units before running')
    pack_ids = [uid for uid, label in units.items() if norm(label) in ('pack', 'paquete', 'envase')]
    pack_id = pack_ids[0] if len(pack_ids) == 1 else None
    catalog = {}
    for p in products:
        catalog.setdefault(norm(p['name']), []).append(p)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS receipt_items (receipt_hash TEXT, line INTEGER, product_id INTEGER, state TEXT NOT NULL, detail TEXT, PRIMARY KEY(receipt_hash,line))')
        conn.commit()
        for i, item in enumerate(receipt['items']):
            name = item['name'].strip()
            old = conn.execute('SELECT state FROM receipt_items WHERE receipt_hash=? AND line=?', (digest, i)).fetchone()
            if old and old[0] in ('imported', 'pending', 'expense'):
                print(f'[{i+1}] SKIP {old[0]} {name}')
                continue
            status, unit, reason = classify(item)
            if status == 'EXPENSE':
                print(f'[{i+1}] {"WOULD RECORD EXPENSE" if args.dry_run else "RECORD EXPENSE"} {name}: {money(dec(item["quantity"]) * dec(item["unit_price"]))} EUR (no stock)')
                if not args.dry_run:
                    conn.execute('INSERT OR REPLACE INTO receipt_items VALUES (?,?,?,?,?)', (digest, i, None, 'expense', json.dumps({'name': name, 'quantity': item['quantity'], 'unit_price': item['unit_price'], 'merchant': receipt['merchant'], 'receipt_date': receipt['receipt_date']}, ensure_ascii=False)))
                    conn.commit()
                continue
            matches = catalog.get(norm(name), [])
            if len(matches) > 1:
                status, reason = 'REVIEW', 'Multiple catalog matches'
            pieces = int(item.get('pieces_per_pack', 1))
            purchased = dec(item.get('purchase_units', item['quantity']))
            if status == 'STOCK' and unit == 4 and pieces != 1:
                status, reason = 'REVIEW', 'Kilograms cannot be converted to pieces'
            if status == 'STOCK' and unit == 2 and pieces > 1 and pack_id is None:
                status, reason = 'REVIEW', 'Create a unique Pack quantity unit in Grocy first'
            if status == 'STOCK' and len(matches) == 1:
                p = matches[0]
                if int(p['qu_id_stock']) != unit:
                    status, reason = 'REVIEW', 'Existing product has different stock unit'
                elif unit == 2:
                    purchase_id = int(p.get('qu_id_purchase') or unit)
                    existing_factor = dec(p.get('qu_factor_purchase_to_stock') or 1)
                    if purchase_id != (pack_id if pieces > 1 else unit) or existing_factor != pieces:
                        status, reason = 'REVIEW', 'Saved purchase conversion differs; review product in Grocy'
            if status == 'REVIEW':
                print(f'[{i+1}] REVIEW {name}: {reason}')
                continue
            existing = len(matches) == 1
            stock_amount = purchased * pieces if unit == 2 else purchased
            print(f'[{i+1}] {"WOULD IMPORT" if args.dry_run else "IMPORT"} {name}: {stock_amount} {units[unit]} ({purchased} purchases × {pieces}) ({"existing" if existing else "NEW"})')
            if args.dry_run:
                continue
            if existing:
                pid = int(matches[0]['id'])
            else:
                # Write-ahead marker before product creation; interrupted attempts need manual reconciliation.
                conn.execute('INSERT OR REPLACE INTO receipt_items VALUES (?,?,?,?,?)', (digest,i,None,'pending','Creating catalog product; verify before retry'))
                conn.commit()
                payload = {'name': name, 'location_id': int(os.getenv('GROCY_LOCATION_ID','2')), 'qu_id_purchase': pack_id if pieces > 1 else unit, 'qu_id_stock': unit, 'min_stock_amount': 0}
                if pieces > 1:
                    payload['qu_factor_purchase_to_stock'] = pieces
                result = grocy('POST', 'objects/products', payload)
                pid = int(result['created_object_id'])
                catalog.setdefault(norm(name), []).append({**payload, 'id': pid})
            conn.execute('INSERT OR REPLACE INTO receipt_items VALUES (?,?,?,?,?)', (digest,i,pid,'pending','Stock write may have happened; verify before retry'))
            conn.commit()
            # Grocy timestamps the purchase on import; source date is preserved in note.
            payload = {'amount': float(stock_amount), 'price': float(money(dec(item['quantity']) * dec(item['unit_price']) / stock_amount)), 'best_before_date': '2999-12-31', 'location_id': int(os.getenv('GROCY_LOCATION_ID','2')), 'note': f'Ticket {receipt["merchant"]} {receipt["receipt_date"]} | {digest[:12]} line {i+1}'}
            grocy('POST', f'stock/products/{pid}/add', payload)
            conn.execute('UPDATE receipt_items SET state=?, detail=? WHERE receipt_hash=? AND line=?', ('imported','',digest,i))
            conn.commit()
    print('Done. Expenses are recorded locally, not in Grocy expense accounting. REVIEW lines were not imported; pending lines require manual reconciliation.')

if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, GrocyError, OSError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)