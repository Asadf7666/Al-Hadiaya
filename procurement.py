"""Stock planning and shared purchase orders, separate from physical goods receipts."""
import datetime as dt,json,math,secrets
STATUSES=('draft','approved','sent','part_received','received','cancelled')
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def migrate(db):
 db.executescript('''CREATE TABLE IF NOT EXISTS inventory_plans(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),location TEXT NOT NULL,supplier_id INTEGER REFERENCES parties(id),lead_days INTEGER NOT NULL DEFAULT 2,cover_days INTEGER NOT NULL DEFAULT 14,safety_stock REAL NOT NULL DEFAULT 0,enabled INTEGER NOT NULL DEFAULT 1,UNIQUE(product_id,location));
 CREATE TABLE IF NOT EXISTS purchase_orders(id TEXT PRIMARY KEY,created TEXT NOT NULL,updated TEXT NOT NULL,supplier_id INTEGER NOT NULL REFERENCES parties(id),location TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',items TEXT NOT NULL,total INTEGER NOT NULL,note TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 0);
 ''')
def planning(db):
 cutoff=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=30)).isoformat()
 demand={(r['product_id'],r['location']):r['used']/30 for r in db.execute("SELECT m.product_id,m.location,-SUM(m.quantity) used FROM movements m JOIN documents d ON d.id=m.reference WHERE d.kind='sale' AND d.reversed=0 AND m.quantity<0 AND julianday(d.date)>=julianday(?) GROUP BY m.product_id,m.location",(cutoff,))}
 stock={(r['product_id'],r['location']):r['quantity'] for r in db.execute('SELECT * FROM stocks')};policies={(r['product_id'],r['location']):dict(r) for r in db.execute('SELECT * FROM inventory_plans')};incoming={}
 for po in db.execute("SELECT location,items FROM purchase_orders WHERE status IN ('approved','sent','part_received')"):
  for item in json.loads(po['items']):key=(item['product_id'],po['location']);incoming[key]=incoming.get(key,0)+max(0,item['quantity']-item['received'])
 rows=[]
 for p in db.execute("SELECT * FROM products WHERE kind<>'recipe' AND (price>0 OR cost>0 OR id IN (SELECT product_id FROM inventory_plans))"):
  for location in ('Warehouse','Outlet'):
   key=(p['id'],location);policy=policies.get(key,{})
   if policy.get('enabled',1)==0:continue
   daily=demand.get(key,0);on_hand=stock.get(key,0);pending=incoming.get(key,0);lead=policy.get('lead_days',2);cover=policy.get('cover_days',14);safety=policy.get('safety_stock',p['minimum'] if location=='Warehouse' else 0)
   target=daily*(lead+cover)+safety;need=max(0,target-on_hand-pending);pack=p['pack'];recommend=math.ceil(max(0,need-0.000001)/pack)*pack
   available_transfer=max(0,stock.get((p['id'],'Warehouse'),0)) if location=='Outlet' else 0
   if not daily and not recommend and not policy:continue
   rows.append({'product_id':p['id'],'name':p['name'],'location':location,'unit':p['unit'],'pack':pack,'daily_demand':round(daily,4),'stock':on_hand,'incoming':pending,'target':round(target,4),'recommended':round(recommend,6),'estimated_cost':round(recommend*p['cost']),'supplier_id':policy.get('supplier_id'),'lead_days':lead,'cover_days':cover,'safety_stock':safety,'days_remaining':round(on_hand/daily,1) if daily else None,'urgent':on_hand<daily*lead+safety,'transfer_available':min(recommend,available_transfer)})
 return sorted(rows,key=lambda r:(not r['urgent'],-r['recommended'],r['name'],r['location']))
def state(db):return {'inventory_plans':[dict(r) for r in db.execute('SELECT * FROM inventory_plans')],'purchase_orders':[dict(r) for r in db.execute('SELECT * FROM purchase_orders ORDER BY created DESC LIMIT 200')],'inventory_planning':planning(db)}
def act(shop,action,data):
 from app import number,money
 with shop.lock,shop.connect() as db:
  before=shop.capture(db)
  if action=='inventory_plan':
   pid=int(data['product_id']);location=shop.location(data.get('location','Warehouse'));supplier=int(data['supplier_id']) if data.get('supplier_id') else None;lead=int(data.get('lead_days',2));cover=int(data.get('cover_days',14));safety=number(data.get('safety_stock',0))
   p=db.execute('SELECT kind FROM products WHERE id=?',(pid,)).fetchone()
   if not p or p['kind']=='recipe' or not 0<=lead<=365 or not 1<=cover<=365:raise ValueError('Choose a stocked product and valid lead/coverage days.')
   if supplier and not db.execute("SELECT 1 FROM parties WHERE id=? AND kind='supplier'",(supplier,)).fetchone():raise ValueError('Choose a supplier.')
   old=db.execute('SELECT id FROM inventory_plans WHERE product_id=? AND location=?',(pid,location)).fetchone();ident=old[0] if old else secrets.randbelow(2**50)+1
   db.execute('INSERT INTO inventory_plans VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET supplier_id=excluded.supplier_id,lead_days=excluded.lead_days,cover_days=excluded.cover_days,safety_stock=excluded.safety_stock,enabled=excluded.enabled',(ident,pid,location,supplier,lead,cover,safety,int(data.get('enabled') in (True,'on'))));result={'id':ident}
  elif action=='purchase_order_create':
   supplier=int(data['supplier_id']);location=shop.location(data.get('location','Warehouse'));items=data.get('items',[]);note=str(data.get('note',''))[:500]
   if not db.execute("SELECT 1 FROM parties WHERE id=? AND kind='supplier'",(supplier,)).fetchone() or not isinstance(items,list) or not 1<=len(items)<=100:raise ValueError('Choose a supplier and 1–100 stocked products.')
   lines=[];seen=set();total=0
   for item in items:
    pid=int(item['product_id']);p=db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone();quantity=number(item['quantity'],True);cost=money(item['price'])
    if not p or p['kind']=='recipe' or pid in seen:raise ValueError('Choose distinct stocked products or café ingredients.')
    seen.add(pid);lines.append({'product_id':pid,'name':p['name'],'unit':p['unit'],'quantity':quantity,'received':0,'cost':cost});total+=round(quantity*cost)
   ident='PO-'+shop.settings(db)['device_id'][:6].upper()+'-'+secrets.token_hex(4).upper();ts=stamp()
   db.execute('INSERT INTO purchase_orders(id,created,updated,supplier_id,location,items,total,note) VALUES(?,?,?,?,?,?,?,?)',(ident,ts,ts,supplier,location,json.dumps(lines),total,note));result={'id':ident}
  elif action=='purchase_order_status':
   row=db.execute('SELECT * FROM purchase_orders WHERE id=?',(str(data.get('id','')),)).fetchone();status=data.get('status')
   allowed={'draft':('approved','cancelled'),'approved':('sent','cancelled'),'sent':('cancelled',),'part_received':('cancelled',)}
   if not row or status not in allowed.get(row['status'],()):raise ValueError('Approve a draft, mark an approved order sent, or cancel outstanding quantities. Receipt status is updated by goods receipts.')
   db.execute('UPDATE purchase_orders SET status=?,updated=?,revision=revision+1 WHERE id=?',(status,stamp(),row['id']));result={'id':row['id']}
  else:raise ValueError('Unknown procurement action.')
  shop.audit(db,action,{k:v for k,v in data.items() if k!='items'});eid=shop.record_event(db,before);shop.queue_updates(db,action,data,result,eid)
 return result
def check_receipt(db,data):
 ident=str(data.get('purchase_order_id',''))
 if not ident:return None
 row=db.execute('SELECT * FROM purchase_orders WHERE id=?',(ident,)).fetchone()
 if not row or row['status'] not in ('approved','sent','part_received') or int(data.get('party_id') or 0)!=row['supplier_id'] or data.get('location')!=row['location']:raise ValueError('Receive against an approved, open purchase order at its supplier/location.')
 ordered={i['product_id']:i for i in json.loads(row['items'])};seen=set()
 for item in data.get('items',[]):
  pid=int(item['product_id']);qty=float(item['quantity'])
  if pid not in ordered or pid in seen or not math.isfinite(qty) or qty<=0 or qty>ordered[pid]['quantity']-ordered[pid]['received']+0.000001:raise ValueError('Receipt exceeds the remaining PO quantity or includes an unordered product.')
  seen.add(pid)
 return row
def receive(db,row,items):
 lines=json.loads(row['items']);added={int(i['product_id']):float(i['quantity']) for i in items}
 for line in lines:line['received']=round(line['received']+added.get(line['product_id'],0),6)
 done=all(i['received']>=i['quantity']-0.000001 for i in lines)
 db.execute('UPDATE purchase_orders SET items=?,status=?,updated=?,revision=revision+1 WHERE id=?',(json.dumps(lines),'received' if done else 'part_received',stamp(),row['id']))
def reverse(db,doc):
 snapshot=json.loads(doc['snapshot']);ident=snapshot.get('purchase_order_id')
 if not ident:return
 row=db.execute('SELECT * FROM purchase_orders WHERE id=?',(ident,)).fetchone()
 if not row:raise ValueError('Linked purchase order is missing.')
 lines=json.loads(row['items']);removed={i['product_id']:i['quantity'] for i in snapshot['items']}
 for line in lines:
  line['received']=round(line['received']-removed.get(line['product_id'],0),6)
  if line['received']<0:raise ValueError('Purchase order receipt conflict. Sync before reversing.')
 status='cancelled' if row['status']=='cancelled' else 'part_received' if any(i['received'] for i in lines) else 'sent'
 db.execute('UPDATE purchase_orders SET items=?,status=?,updated=?,revision=revision+1 WHERE id=?',(json.dumps(lines),status,stamp(),ident))
def validate_plan(row):
 if row['location'] not in ('Warehouse','Outlet') or type(row['lead_days']) is not int or not 0<=row['lead_days']<=365 or type(row['cover_days']) is not int or not 1<=row['cover_days']<=365 or not math.isfinite(row['safety_stock']) or row['safety_stock']<0 or row['enabled'] not in (0,1):raise ValueError('Invalid inventory planning policy.')
def validate_receipts(payload):
 for doc in payload['masters'].get('documents',[]):
  ident=json.loads(doc['snapshot']).get('purchase_order_id')
  if ident and (doc['kind']!='purchase' or not any(p['id']==ident for p in payload['masters'].get('purchase_orders',[]))):raise ValueError('Linked receipt must include its purchase order update.')
def validate_change(db,row,payload):
 permitted={r[1] for r in db.execute('PRAGMA table_info(purchase_orders)')}
 if set(row)!=permitted or row['status'] not in STATUSES or row['location'] not in ('Warehouse','Outlet') or type(row['revision']) is not int or row['revision']<0:raise ValueError('Invalid purchase order.')
 lines=json.loads(row['items'])
 if not isinstance(lines,list) or not 1<=len(lines)<=100 or len({i['product_id'] for i in lines})!=len(lines):raise ValueError('Invalid purchase order lines.')
 for i in lines:
  if not math.isfinite(i['quantity']) or i['quantity']<=0 or not math.isfinite(i['received']) or not 0<=i['received']<=i['quantity']+0.000001 or type(i['cost']) is not int or i['cost']<0:raise ValueError('Invalid purchase order quantities or cost.')
 if type(row['total']) is not int or row['total']!=sum(round(i['quantity']*i['cost']) for i in lines):raise ValueError('Invalid purchase order total.')
 old=db.execute('SELECT * FROM purchase_orders WHERE id=?',(row['id'],)).fetchone()
 if not old:
  if row['revision']!=0 or row['status']!='draft' or any(i['received'] for i in lines):raise ValueError('New purchase orders must be unreceived drafts.')
  return
 if row['revision']!=old['revision']+1:raise ValueError('Purchase order changed on another node. Sync and reconcile before retrying.')
 for k in ('supplier_id','location','created','total','note'):
  if row[k]!=old[k]:raise ValueError('Purchase order terms cannot change after creation.')
 previous=json.loads(old['items'])
 if [{k:v for k,v in i.items() if k!='received'} for i in lines]!=[{k:v for k,v in i.items() if k!='received'} for i in previous]:raise ValueError('Purchase order lines cannot change after creation.')
 expected={i['product_id']:0 for i in lines};has_receipt=False
 for doc in payload['masters'].get('documents',[]):
  snap=json.loads(doc['snapshot'])
  if snap.get('purchase_order_id')!=row['id']:continue
  has_receipt=True
  if doc['kind']!='purchase' or doc['party_id']!=row['supplier_id'] or doc['location']!=row['location']:raise ValueError('Purchase order receipt does not match supplier/location.')
  prior=db.execute('SELECT reversed FROM documents WHERE id=?',(doc['id'],)).fetchone()
  if prior and (prior['reversed'] or not doc['reversed']):raise ValueError('Invalid repeated purchase order receipt.')
  for i in snap['items']:
   if i['product_id'] not in expected:raise ValueError('Receipt contains an unordered product.')
   expected[i['product_id']]+=i['quantity']*(-1 if prior else 1)
 for before,after in zip(previous,lines):
  if abs(after['received']-before['received']-expected[after['product_id']])>0.000001:raise ValueError('Purchase order received quantities require matching purchase invoices.')
 if has_receipt:
  if not any(expected.values()):raise ValueError('Empty goods receipt.')
  if any(v>0 for v in expected.values()) and old['status'] not in ('approved','sent','part_received'):raise ValueError('Purchase order is not open for receipt.')
  status='cancelled' if old['status']=='cancelled' else 'received' if all(i['received']>=i['quantity']-0.000001 for i in lines) else 'part_received' if any(i['received'] for i in lines) else 'sent'
  if row['status']!=status:raise ValueError('Purchase order receipt status differs from quantities.')
 elif row['status'] not in {'draft':('approved','cancelled'),'approved':('sent','cancelled'),'sent':('cancelled',),'part_received':('cancelled',)}.get(old['status'],()):raise ValueError('Invalid purchase order status transition.')
