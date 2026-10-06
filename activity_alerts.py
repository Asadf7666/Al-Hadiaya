"""Itemised internal business activity. No customer-facing promotion or secret content."""
import json

def units(n):return f'{n:g}'
def chunks(text,limit=2800):
 pages=[];current=''
 for line in text.splitlines():
  # User-supplied descriptions are bounded; split a pathological long line safely too.
  while len(line)>limit:
   if current:pages.append(current);current=''
   pages.append(line[:limit]);line=line[limit:]
  if len(current)+len(line)+1>limit:pages.append(current);current=''
  current+=('\n' if current else '')+line
 if current:pages.append(current)
 return pages or ['Business activity saved.']
def summary(shop,db,action,data,result,eid):
 s=shop.settings(db);lines=[]
 event=db.execute('SELECT payload FROM sync_events WHERE id=?',(eid.split(':',1)[0],)).fetchone()
 payload=json.loads(event[0]) if event else None
 # Synced event IDs use ':' suffixes for individual actions; their base is stable.
 if action in ('sale','purchase'):
  enabled='whatsapp_sales' if action=='sale' else 'whatsapp_purchases'
  if not s.get(enabled):return ''
  doc=db.execute('SELECT * FROM documents WHERE id=?',(result.get('id'),)).fetchone()
  if not doc:return ''
  snapshot=json.loads(doc['snapshot']);customer=snapshot.get('party') or {};lines=[action.title()+' invoice '+doc['id']+' · '+doc['location'], 'Customer: '+customer.get('name','Walk-in') if action=='sale' else 'Supplier: '+customer.get('name','Supplier')]
  if customer.get('phone'):lines.append('Mobile: '+customer['phone'])
  for item in snapshot['items']:
   lines.append(f"• {item['name']} [{item['sku']}]: {units(item['quantity'])} {item['unit']} × INR {item['price']/100:.2f} = INR {item['total']/100:.2f}")
  lines.extend([f"Total INR {doc['total']/100:.2f} · tax INR {doc['tax']/100:.2f} · discount INR {doc['discount']/100:.2f}",f"Paid INR {doc['paid']/100:.2f} via {doc['payment']} · invoice due INR {(doc['total']-doc['paid'])/100:.2f}"])
  if customer.get('id'):
   row=db.execute('SELECT balance FROM parties WHERE id=?',(customer['id'],)).fetchone()
   if row:lines.append(f"Current ledger due INR {row[0]/100:.2f}")
 elif action=='party':
  if not s.get('whatsapp_profiles'):return ''
  p=db.execute('SELECT * FROM parties WHERE id=?',(result.get('id') or data.get('id'),)).fetchone()
  if not p:return ''
  label=('updated' if data.get('id') else 'created') if data.get('_local') else 'saved'
  lines=[p['kind'].title()+' profile '+label+': '+p['name'], 'Mobile: '+(p['phone'] or 'Not provided'), 'Price tier: '+p['price_tier'],f"Credit limit INR {p['credit_limit']/100:.2f} · current due INR {p['balance']/100:.2f}"]
  if p['address']:lines.append('Address: '+p['address'])
  if p['gstin']:lines.append('GSTIN: '+p['gstin'])
 elif action in ('product','import_products'):
  if not s.get('whatsapp_catalogue'):return ''
  rows=(payload or {}).get('masters',{}).get('products',[])
  if not rows and result.get('id'):
   p=db.execute('SELECT * FROM products WHERE id=?',(result['id'],)).fetchone();rows=[dict(p)] if p else []
  lines=['Inventory catalogue saved: '+str(len(rows))+' product(s)']
  for p in rows:lines.append(f"• {p['name']} [{p['sku']}] · retail INR {p['price']/100:.2f} · wholesale INR {p['wholesale_price']/100:.2f} · {p['pack']:g} units/pack · GST {p['gst']:g}%")
 elif action=='recipe':
  if not s.get('whatsapp_recipes'):return ''
  p=db.execute('SELECT name FROM products WHERE id=?',(data.get('product_id'),)).fetchone()
  if not p:return ''
  lines=['Recipe saved: '+p['name']]
  for r in db.execute('SELECT p.name,p.unit,r.quantity FROM recipes r JOIN products p ON p.id=r.ingredient_id WHERE r.product_id=?',(data['product_id'],)):lines.append(f"• {r['name']}: {units(r['quantity'])} {r['unit']} per serving")
 elif action=='adjust':
  if not s.get('whatsapp_stock'):return ''
  lines=['Stock adjustment · '+str(data.get('location','Warehouse')), 'Reason: '+str(data.get('note',''))]
 elif action=='transfer':
  if not s.get('whatsapp_transfers'):return ''
  p=db.execute('SELECT name,unit FROM products WHERE id=?',(data.get('product_id'),)).fetchone()
  if not p:return ''
  lines=[f"Stock transfer {result.get('id','')}: {p['name']} · {units(float(data['quantity']))} {p['unit']}",str(data['source'])+' → '+str(data['target'])]
 elif action=='payment':
  if not s.get('whatsapp_payments'):return ''
  p=db.execute('SELECT name,kind,phone,balance FROM parties WHERE id=?',(data.get('party_id'),)).fetchone()
  if not p:return ''
  lines=[p['kind'].title()+' payment: '+p['name'],f"INR {float(data['amount']):.2f} via {data.get('payment') or data.get('method','Cash')}", f"Current ledger due INR {p['balance']/100:.2f}",'Note: '+str(data.get('note',''))]
 elif action=='expense':
  if not s.get('whatsapp_expenses'):return ''
  lines=['Expense: '+str(data.get('name','')),f"INR {float(data['amount']):.2f} · {data.get('payment') or data.get('method','Cash')}", 'Note: '+str(data.get('note',''))]
 elif action=='reverse':
  if not s.get('whatsapp_reversals'):return ''
  doc=db.execute('SELECT * FROM documents WHERE id=?',(data.get('id'),)).fetchone()
  if not doc:return ''
  lines=['Invoice reversed: '+doc['id']+' · '+doc['location'], f"INR {doc['total']/100:.2f}", 'Reason: '+str(data.get('reason','Synced reversal'))]
  for item in json.loads(doc['snapshot'])['items']:lines.append(f"• {item['name']}: {units(item['quantity'])} {item['unit']}")
 elif action in ('inventory_plan','purchase_order_create','purchase_order_status'):
  if not s.get('whatsapp_purchases'):return ''
  if action=='inventory_plan':
   p=db.execute('SELECT name FROM products WHERE id=?',(data['product_id'],)).fetchone();lines=['Stock planning saved: '+p['name']+' · '+data.get('location','Warehouse')]
  else:
   po=db.execute('SELECT * FROM purchase_orders WHERE id=?',(result.get('id'),)).fetchone()
   if not po:return ''
   supplier=db.execute('SELECT name FROM parties WHERE id=?',(po['supplier_id'],)).fetchone()
   lines=['Purchase order '+po['id']+' · '+po['status'].replace('_',' '),supplier['name']+' · '+po['location']]
   for i in json.loads(po['items']):lines.append(f"• {i['name']}: ordered {units(i['quantity'])}, received {units(i['received'])} {i['unit']}")
   lines.append(f"Estimated INR {po['total']/100:.2f}; stock and supplier dues change on receipt.")
 else:return ''
 if payload:
  for delta in payload['deltas']['stocks']:
   p=db.execute('SELECT name,unit,kind FROM products WHERE id=?',(delta['product_id'],)).fetchone()
   current=db.execute('SELECT quantity FROM stocks WHERE product_id=? AND location=?',(delta['product_id'],delta['location'])).fetchone()
   if p and current:
    change=delta['delta'];word='added' if change>0 else 'deducted'
    lines.append(f"Stock {p['name']} · {delta['location']}: {units(abs(change))} {p['unit']} {word}; {units(current[0]-change)} → {units(current[0])} {p['unit']}")
 return '\n'.join(lines)

def daily(shop,db,local_now):
 import datetime as dt
 day=local_now.date()
 def is_today(value):return dt.datetime.fromisoformat(value).astimezone(local_now.tzinfo).date()==day
 docs=[dict(r) for r in db.execute('SELECT * FROM documents WHERE reversed=0') if is_today(r['date'])];lines=[f'Daily internal summary · {day}', 'Includes records available at last sync. Late offline entries appear after sync; queued summaries are snapshots.']
 for location in ('Warehouse','Outlet'):
  sales=[d for d in docs if d['kind']=='sale' and d['location']==location];purchases=[d for d in docs if d['kind']=='purchase' and d['location']==location]
  lines.append(f"{location}: {len(sales)} sale bills · sales INR {sum(d['total'] for d in sales)/100:.2f} · GST INR {sum(d['tax'] for d in sales)/100:.2f} · new credit INR {sum(d['total']-d['paid'] for d in sales)/100:.2f}")
  lines.append(f"Purchases INR {sum(d['total'] for d in purchases)/100:.2f} · paid INR {sum(d['paid'] for d in purchases)/100:.2f}")
  for method in ('Cash','UPI','Card','Bank'):
   amount=sum(d['paid'] for d in sales if d['payment']==method)
   if amount:lines.append(f'{method} received at billing INR {amount/100:.2f}')
  sold={}
  for doc in sales:
   for i in json.loads(doc['snapshot'])['items']:
    key=(i['name'],i['unit']);sold[key]=sold.get(key,0)+i['quantity']
  for (name,unit),q in sorted(sold.items()):lines.append(f'• Sold {name}: {units(q)} {unit}')
 expenses=[r for r in db.execute('SELECT * FROM expenses') if is_today(r['date'])];lines.append(f"Expenses INR {sum(r['amount'] for r in expenses)/100:.2f}")
 payments=[r for r in db.execute('SELECT p.*,a.kind FROM payments p JOIN parties a ON a.id=p.party_id') if is_today(r['date'])]
 for kind in ('customer','supplier'):lines.append(f"{kind.title()} payments INR {sum(r['amount'] for r in payments if r['kind']==kind)/100:.2f}")
 profiles=[r for r in db.execute("SELECT * FROM audit WHERE action='party'") if is_today(r['date'])];lines.append(f'Customer / supplier profile changes: {len(profiles)} (local audit only)')
 for kind in ('customer','supplier'):
  due=db.execute('SELECT COALESCE(SUM(balance),0) FROM parties WHERE kind=?',(kind,)).fetchone()[0];lines.append(f'{kind.title()} outstanding INR {due/100:.2f}')
 stock={}
 for m in db.execute('SELECT m.*,p.name,p.unit FROM movements m JOIN products p ON p.id=m.product_id'):
  if is_today(m['date']):
   key=(m['name'],m['unit'],m['location'],'added' if m['quantity']>0 else 'deducted');stock[key]=stock.get(key,0)+abs(m['quantity'])
 for (name,unit,location,direction),q in sorted(stock.items()):lines.append(f'• Stock {direction}: {name} · {location}: {units(q)} {unit}')
 from stock_alerts import alerts
 for a in alerts(db,shop.settings(db)):lines.append('⚠ '+a['message'])
 from procurement import planning
 for r in planning(db):
  if r['recommended']:lines.append(f"Plan {r['name']} · {r['location']}: {units(r['recommended'])} {r['unit']}; estimated INR {r['estimated_cost']/100:.2f}, open incoming {units(r['incoming'])}")
 orders=db.execute("SELECT COUNT(*) FROM purchase_orders WHERE status IN ('approved','sent','part_received')").fetchone()[0];lines.append(f'Open purchase orders: {orders}')
 return '\n'.join(lines)
