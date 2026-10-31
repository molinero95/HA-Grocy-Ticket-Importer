#!/usr/bin/env python3
"""Extract structured receipt data from PDF/JPEG/PNG with OpenAI Responses API."""
import argparse
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import urllib.request
from decimal import Decimal, ROUND_HALF_UP

SCHEMA = {
  'type':'object','additionalProperties':False,
  'required':['merchant','receipt_date','total','items'],
  'properties':{
    'merchant':{'type':'string'},'receipt_date':{'type':'string'},'total':{'type':'number'},
    'items':{'type':'array','items':{'type':'object','additionalProperties':False,
      'required':['name','quantity','unit_price','ambiguous','reason'],
      'properties':{'name':{'type':'string'},'quantity':{'type':'number'},'unit_price':{'type':'number'},'ambiguous':{'type':'boolean'},'reason':{'type':'string'}}}}
  }
}

def extract(path):
    api_key = os.environ['OPENAI_API_KEY']
    raw = path.read_bytes()
    if len(raw)>12*1024*1024: raise ValueError('File too large (12 MiB limit)')
    mime = {'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'}.get(path.suffix.lower())
    if not mime: raise ValueError('Supported formats: PDF, JPG, PNG')
    data_url = 'data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')
    part = ({'type':'input_file','filename':path.name,'file_data':data_url} if mime=='application/pdf'
            else {'type':'input_image','image_url':data_url})
    payload = {
      'model':os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),
      'store':False,
      'instructions':('Extract supermarket receipt line items faithfully. Do not invent product variants, EANs, or expiry dates. '
       'Return quantity and unit_price; when receipt shows line total for multiple units, divide exactly. '
       'Mark ambiguous=true for unclear products, missing prices, uncertain quantity, or discounts not attributable to lines. '
       'Do not include loyalty balances, payment, personal identifiers, or VAT summaries as products. '
       'Use YYYY-MM-DD for receipt_date; if unknown, return empty string. '
       'Use the actual payable receipt total, accounting for discounts. Keep reason empty for unambiguous lines.'),
      'input':[{'role':'user','content':[{'type':'input_text','text':'Read this receipt and extract purchase lines.'},part]}],
      'text':{'format':{'type':'json_schema','name':'receipt','strict':True,'schema':SCHEMA}}
    }
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode(),
      headers={'Authorization':'Bearer '+api_key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=120) as response: result=json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError('OpenAI API error HTTP '+str(exc.code)) from None
    content=[c['text'] for item in result.get('output',[]) for c in item.get('content',[]) if c.get('type')=='output_text']
    if not content: raise ValueError('No structured output from model')
    receipt=json.loads(''.join(content))
    receipt['source_sha256']=hashlib.sha256(raw).hexdigest()
    # If extraction is uncertain, preserve lines for review instead of committing a partial receipt.
    try:
        cent = Decimal('0.01')
        summed = sum((Decimal(str(i['quantity'])) * Decimal(str(i['unit_price']))).quantize(cent, rounding=ROUND_HALF_UP) for i in receipt['items'])
        if summed != Decimal(str(receipt['total'])).quantize(cent, rounding=ROUND_HALF_UP):
            for item in receipt['items']:
                item['ambiguous']=True
                item['reason']=(item.get('reason','')+' Receipt total mismatch').strip()
    except Exception:
        for item in receipt['items']:
            item['ambiguous']=True
            item['reason']='Invalid extracted numeric value'
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('receipt',type=Path);p.add_argument('-o','--output',type=Path);args=p.parse_args()
    parsed=extract(args.receipt)
    target=args.output or args.receipt.with_suffix('.json')
    target.write_text(json.dumps(parsed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Saved '+str(target)+'; review flags: '+str(sum(bool(i['ambiguous']) for i in parsed['items'])))