"""Readable WhatsApp activity and daily summaries, with bounded detail pages."""
import json

def units(n):return f'{n:g}'
def rupees(n):return f'₹{n/100:,.2f}'
def chunks(text,limit=2200):
 pages=[];current=''
 for line in text.splitlines():
  while len(line)>limit:
   if current:pages.append(current);current=''
   pages.append(line[:limit]);line=line[limit:]
  if len(current)+len(line)+1>limit:pages.append(current);current=''
  current+=('\n' if current else '')+line
 if current:pages.append(current)
 return pages or ['Business activity saved.']
def summary(shop,db,action,data,result,eid):
 s=shop.settings(db);lines=[]
 event=db.execute('SELECT payload FROM sync_events WHERE id=?',(eid.split(':',1)[0],)).fetchone();payload=json.loads(event[0]) if event else None
 if action in ('sale','purchase'):
  if not s.get('whatsapp_sales' if action=='sale' else 'whatsapp_purchases'):return ''
  doc=db.execute('SELECT * FROM documents WHERE id=?',(result.get('id'),)).fetchone()
  if not doc:return ''
  snap=json.loads(doc['snapshot']);party=snap.get('party') or {}
  lines=[f"*{'SALE COMPLETED' if action=='sale' else 'STOCK RECEIVED'}*",f"Invoice: {doc['id']}",f"Location: {doc['location']}",('Customer: ' if action=='sale' else 'Supplier: ')+party.get('name','Walk-in')]
  if party.get('phone'):lines.append('Mobile: '+party['phone'])
  lines+=['','*Items*']
  for i in snap['items']:lines += [f"• *{i['name']}*",f"  {units(i['quantity'])} {i['unit']} × {rupees(i['price'])} = {rupees(i['total'])}"]
  lines+=['',f"*Total: {rupees(doc['total'])}*"]
  if doc['tax']:lines.append('Tax included: '+rupees(doc['tax']))
  if doc['discount']:lines.append('Discount: '+rupees(doc['discount']))
  lines += [f"Paid: {rupees(doc['paid'])} ({doc['payment']})",f"Invoice due: {rupees(doc['total']-doc['paid'])}"]
  if party.get('id'):
   row=db.execute('SELECT balance FROM parties WHERE id=?',(party['id'],)).fetchone()
   if row:lines.append('Total account due: '+rupees(row[0]))
  if snap.get('purchase_order_id'):lines+=['','Purchase order: '+snap['purchase_order_id']]
 elif action=='party':
  if not s.get('whatsapp_profiles'):return ''
  p=db.execute('SELECT * FROM parties WHERE id=?',(result.get('id') or data.get('id'),)).fetchone()
  if not p:return ''
  label=('updated' if data.get('id') else 'created') if data.get('_local') else 'saved'
  lines=[f"*{p['kind'].upper()} PROFILE {label.upper()}*",'',f"*{p['name']}*",'Mobile: '+(p['phone'] or 'Not provided'),'Pricing: '+p['price_tier'].title(),'', '*Account*','Credit limit: '+(rupees(p['credit_limit']) if p['credit_limit'] else 'Not set'),'Outstanding: '+rupees(p['balance'])]
  if p['address']:lines+=['','Address: '+p['address']]
  if p['gstin']:lines.append('GSTIN: '+p['gstin'])
 elif action in ('product','import_products'):
  if not s.get('whatsapp_catalogue'):return ''
  rows=(payload or {}).get('masters',{}).get('products',[])
  if not rows and result.get('id'):
   p=db.execute('SELECT * FROM products WHERE id=?',(result['id'],)).fetchone();rows=[dict(p)] if p else []
  lines=['*CATALOGUE UPDATED*',f'{len(rows)} product(s) saved']
  for p in rows:lines += ['',f"• *{p['name']}*",f"SKU: {p['sku']}",f"Retail {rupees(p['price'])} | Wholesale {rupees(p['wholesale_price'])}",f"Pack: {p['pack']:g} units | GST: {p['gst']:g}%"]
 elif action=='recipe':
  if not s.get('whatsapp_recipes'):return ''
  p=db.execute('SELECT name FROM products WHERE id=?',(data.get('product_id'),)).fetchone()
  if not p:return ''
  lines=['*RECIPE UPDATED*',p['name'],'','*Ingredients per serving*']
  for r in db.execute('SELECT p.name,p.unit,r.quantity FROM recipes r JOIN products p ON p.id=r.ingredient_id WHERE r.product_id=?',(data['product_id'],)):lines.append(f"• {r['name']}: {units(r['quantity'])} {r['unit']}")
 elif action=='adjust':
  if not s.get('whatsapp_stock'):return ''
  lines=['*STOCK ADJUSTMENT*','Location: '+str(data.get('location','Warehouse')),'Reason: '+str(data.get('note',''))]
 elif action=='transfer':
  if not s.get('whatsapp_transfers'):return ''
  p=db.execute('SELECT name,unit FROM products WHERE id=?',(data.get('product_id'),)).fetchone()
  if not p:return ''
  lines=['*STOCK TRANSFER*',f"Reference: {result.get('id','')}",f"{data['source']} → {data['target']}",'',f"*{p['name']}*",f"Quantity: {units(float(data['quantity']))} {p['unit']}"]
 elif action=='payment':
  if not s.get('whatsapp_payments'):return ''
  p=db.execute('SELECT name,kind,phone,balance FROM parties WHERE id=?',(data.get('party_id'),)).fetchone()
  if not p:return ''
  lines=[f"*{p['kind'].upper()} PAYMENT*",p['name'],'',f"Amount: {rupees(round(float(data['amount'])*100))}",'Method: '+str(data.get('payment') or data.get('method','Cash')),'Account due: '+rupees(p['balance'])]
  if data.get('note'):lines+=['','Note: '+str(data['note'])]
 elif action=='expense':
  if not s.get('whatsapp_expenses'):return ''
  lines=['*EXPENSE RECORDED*',str(data.get('name','')),'',f"Amount: {rupees(round(float(data['amount'])*100))}",'Method: '+str(data.get('payment') or data.get('method','Cash'))]
 elif action=='reverse':
  if not s.get('whatsapp_reversals'):return ''
  doc=db.execute('SELECT * FROM documents WHERE id=?',(data.get('id'),)).fetchone()
  if not doc:return ''
  lines=['*INVOICE REVERSED*','Invoice: '+doc['id'],'Location: '+doc['location'],'Amount: '+rupees(doc['total']),'Reason: '+str(data.get('reason','Synced reversal')),'','*Items*']
  for i in json.loads(doc['snapshot'])['items']:lines.append(f"• {i['name']}: {units(i['quantity'])} {i['unit']}")
 elif action in ('inventory_plan','purchase_order_create','purchase_order_status'):
  if not s.get('whatsapp_purchases'):return ''
  if action=='inventory_plan':
   p=db.execute('SELECT name FROM products WHERE id=?',(data['product_id'],)).fetchone();lines=['*STOCK POLICY UPDATED*',p['name'],'Location: '+data.get('location','Warehouse')]
  else:
   po=db.execute('SELECT * FROM purchase_orders WHERE id=?',(result.get('id'),)).fetchone()
   if not po:return ''
   supplier=db.execute('SELECT name FROM parties WHERE id=?',(po['supplier_id'],)).fetchone()
   lines=['*PURCHASE ORDER UPDATE*','Order: '+po['id'],'Status: '+po['status'].replace('_',' ').title(),'Supplier: '+supplier['name'],'Location: '+po['location'],'','*Items*']
   for i in json.loads(po['items']):lines += [f"• *{i['name']}*",f"  Ordered: {units(i['quantity'])} {i['unit']}",f"  Received: {units(i['received'])} | Remaining: {units(i['quantity']-i['received'])}"]
   lines+=['','Estimated value: '+rupees(po['total']),'Stock and supplier dues change when goods are received.']
 else:return ''
 if payload and payload['deltas']['stocks']:
  lines+=['','*Stock movement*']
  for delta in payload['deltas']['stocks']:
   p=db.execute('SELECT name,unit FROM products WHERE id=?',(delta['product_id'],)).fetchone();current=db.execute('SELECT quantity FROM stocks WHERE product_id=? AND location=?',(delta['product_id'],delta['location'])).fetchone()
   if p and current:
    change=delta['delta'];word='Added' if change>0 else 'Deducted'
    lines += [f"• *{p['name']}* ({delta['location']})",f"  {word}: {units(abs(change))} {p['unit']}",f"  Before: {units(current[0]-change)} → Now: {units(current[0])} {p['unit']}"]
 return '\n'.join(lines)

def daily(shop,db,local_now):
 import datetime as dt
 day=local_now.date()
 def is_today(value):return dt.datetime.fromisoformat(value).astimezone(local_now.tzinfo).date()==day
 docs=[dict(r) for r in db.execute('SELECT * FROM documents WHERE reversed=0') if is_today(r['date'])]
 lines=['*DAILY BUSINESS SUMMARY*',local_now.strftime('%d %b %Y'),'']
 for location in ('Warehouse','Outlet'):
  sales=[d for d in docs if d['kind']=='sale' and d['location']==location];purchases=[d for d in docs if d['kind']=='purchase' and d['location']==location]
  lines += [f'*{location}*',f"Sales: *{rupees(sum(d['total'] for d in sales))}* ({len(sales)} bills)",f"Received at billing: {rupees(sum(d['paid'] for d in sales))}",f"New sale credit: {rupees(sum(d['total']-d['paid'] for d in sales))}",f"Tax included: {rupees(sum(d['tax'] for d in sales))}",f"Purchases: {rupees(sum(d['total'] for d in purchases))}",f"Paid to suppliers at billing: {rupees(sum(d['paid'] for d in purchases))}"]
  for method in ('Cash','UPI','Card','Bank'):
   amount=sum(d['paid'] for d in sales if d['payment']==method)
   if amount:lines.append(f'• {method}: {rupees(amount)} received')
  sold={}
  for doc in sales:
   for i in json.loads(doc['snapshot'])['items']:
    key=(i['name'],i['unit']);sold[key]=sold.get(key,0)+i['quantity']
  if sold:
   lines+=['','*Items sold*']
   for (name,unit),q in sorted(sold.items()):lines.append(f'• Sold {name}: {units(q)} {unit}')
  lines.append('')
 expenses=[r for r in db.execute('SELECT * FROM expenses') if is_today(r['date'])];payments=[r for r in db.execute('SELECT p.*,a.kind FROM payments p JOIN parties a ON a.id=p.party_id') if is_today(r['date'])]
 lines+=['*Accounts*','Expenses: '+rupees(sum(r['amount'] for r in expenses))]
 for kind in ('customer','supplier'):
  lines.append(f"{kind.title()} payments: {rupees(sum(r['amount'] for r in payments if r['kind']==kind))}")
  due=db.execute('SELECT COALESCE(SUM(balance),0) FROM parties WHERE kind=?',(kind,)).fetchone()[0];lines.append(f'{kind.title()} outstanding: {rupees(due)}')
 profiles=[r for r in db.execute("SELECT * FROM audit WHERE action='party'") if is_today(r['date'])];lines+=['',f'Profile changes: {len(profiles)} (local audit)']
 stock={}
 for m in db.execute('SELECT m.*,p.name,p.unit FROM movements m JOIN products p ON p.id=m.product_id'):
  if is_today(m['date']):
   key=(m['name'],m['unit'],m['location'],'added' if m['quantity']>0 else 'deducted');stock[key]=stock.get(key,0)+abs(m['quantity'])
 if stock:lines+=['','*Stock movements*']
 for (name,unit,location,direction),q in sorted(stock.items()):lines += [f'• Stock {direction}: {name}',f'  {location}: {units(q)} {unit}']
 from stock_alerts import alerts
 alert_rows=alerts(db,shop.settings(db))
 if alert_rows:lines+=['','*Stock needs attention*']
 for a in alert_rows:lines.append('• '+a['message'])
 from procurement import planning
 plans=[r for r in planning(db) if r['recommended']]
 if plans:lines+=['','*Replenishment plan*']
 for r in plans:lines += [f"• *{r['name']}* ({r['location']})",f"  Suggested: {units(r['recommended'])} {r['unit']}",f"  Incoming: {units(r['incoming'])} | Estimate: {rupees(r['estimated_cost'])}"]
 orders=db.execute("SELECT COUNT(*) FROM purchase_orders WHERE status IN ('approved','sent','part_received')").fetchone()[0]
 lines+=['',f'Open purchase orders: {orders}','','_Based on records received by last sync._']
 return '\n'.join(lines)
