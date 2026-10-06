"""Native WhatsApp trading carts, deterministic automation and shared order workflow."""
import csv,datetime as dt,hashlib,io,json,re,secrets,urllib.request,urllib.error
from decimal import Decimal
from notifications import whatsapp_number,read_token
STATUSES=('new','needs_review','confirmed','packing','ready','completed','cancelled')
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def migrate(db):
 db.executescript('''
 CREATE TABLE IF NOT EXISTS trade_orders(id TEXT PRIMARY KEY,created TEXT NOT NULL,updated TEXT NOT NULL,source_id TEXT UNIQUE NOT NULL,name TEXT NOT NULL,phone TEXT NOT NULL,location TEXT NOT NULL DEFAULT 'Warehouse',status TEXT NOT NULL DEFAULT 'new',items TEXT NOT NULL,total INTEGER NOT NULL DEFAULT 0,issues TEXT NOT NULL DEFAULT '[]',raw_order TEXT NOT NULL,catalog_id TEXT NOT NULL,invoice_id TEXT NOT NULL DEFAULT '',contact_allowed INTEGER NOT NULL DEFAULT 1);
 CREATE TABLE IF NOT EXISTS commerce_products(id INTEGER PRIMARY KEY,catalog_id TEXT NOT NULL,retailer_id TEXT NOT NULL,product_id INTEGER NOT NULL REFERENCES products(id),units INTEGER NOT NULL DEFAULT 1,price_tier TEXT NOT NULL DEFAULT 'retail',active INTEGER NOT NULL DEFAULT 1,UNIQUE(catalog_id,retailer_id));
 CREATE TABLE IF NOT EXISTS whatsapp_sessions(phone TEXT PRIMARY KEY,name TEXT NOT NULL,last_message INTEGER NOT NULL,stopped INTEGER NOT NULL DEFAULT 0);
 ''')
 for col,kind in [('message_type',"TEXT NOT NULL DEFAULT 'template'"),('payload',"TEXT NOT NULL DEFAULT '{}'"),('order_id',"TEXT NOT NULL DEFAULT ''")]:
  if col not in {r[1] for r in db.execute('PRAGMA table_info(notifications)')}:db.execute('ALTER TABLE notifications ADD COLUMN '+col+' '+kind)
 for k,v in {'whatsapp_catalogue_id':'','whatsapp_commerce_enabled':False,'whatsapp_catalogue_checked':'','whatsapp_order_template':'al_hadiya_order_update','whatsapp_catalogue_reply':True}.items():db.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,json.dumps(v)))
def window(db,phone):
 row=db.execute('SELECT * FROM whatsapp_sessions WHERE phone=?',(phone,)).fetchone()
 return bool(row and not row['stopped'] and 0<=dt.datetime.now(dt.timezone.utc).timestamp()-row['last_message']<86340)
def state(db):
 return {'trade_orders':[dict(r) for r in db.execute('SELECT * FROM trade_orders ORDER BY created DESC LIMIT 200')],'commerce_products':[dict(r) for r in db.execute('SELECT * FROM commerce_products')],'whatsapp_sessions':[dict(r) for r in db.execute('SELECT * FROM whatsapp_sessions ORDER BY last_message DESC LIMIT 50')]}
def api(shop,path,data=None):
 with shop.connect() as db:s=shop.settings(db)
 token=read_token(shop.folder)
 if not token or not re.fullmatch(r'v\d+\.\d+',s['whatsapp_api_version']):raise ValueError('Configure a valid WhatsApp sender credential and Graph version.')
 if not re.fullmatch(r'[0-9A-Za-z_/?=.,&-]+',path):raise ValueError('Invalid Meta API path.')
 req=urllib.request.Request('https://graph.facebook.com/'+s['whatsapp_api_version']+'/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)
 except urllib.error.HTTPError as e:
  try:code=json.load(e).get('error',{}).get('code','unknown')
  except Exception:code='unknown'
  raise ValueError('Meta rejected catalogue setup (HTTP '+str(e.code)+', code '+str(code)+'). Check catalogue ownership and business_management/catalog_management access.') from None
 except (urllib.error.URLError,OSError,TimeoutError):raise ValueError('Meta is unavailable. Retry catalogue setup when connected.') from None

def price_lines(db,raw,catalog_id):
 lines=[];issues=[];seen=set();total=0
 items=raw.get('product_items',[])
 if not isinstance(items,list) or not 1<=len(items)<=30:raise ValueError('WhatsApp carts must contain 1 to 30 lines.')
 for item in items:
  rid=str(item.get('product_retailer_id',''))[:100];quantity=Decimal(str(item.get('quantity',0)))
  if not quantity.is_finite() or quantity!=quantity.to_integral_value() or not 1<=quantity<=1000 or rid in seen:raise ValueError('Invalid WhatsApp cart quantity or duplicate item.')
  seen.add(rid);q=int(quantity)
  mapping=db.execute('SELECT m.*,p.name,p.price,p.wholesale_price,p.kind FROM commerce_products m JOIN products p ON p.id=m.product_id WHERE m.catalog_id=? AND m.retailer_id=? AND m.active=1',(catalog_id,rid)).fetchone()
  currency=str(item.get('currency',''))
  quoted=Decimal(str(item.get('item_price',0)))
  if not quoted.is_finite() or quoted<0:raise ValueError('Invalid quoted price.')
  line={'retailer_id':rid,'catalogue_quantity':q,'quoted_price':str(quoted),'currency':currency}
  if not mapping:issues.append('Unmapped catalogue item: '+rid);line.update(name=rid,product_id=None,quantity=q,price=0,tier='retail')
  else:
   unit_price=mapping['wholesale_price'] if mapping['price_tier']=='wholesale' and mapping['wholesale_price']>0 else mapping['price']
   units=mapping['units'];base_quantity=q*units
   line.update(name=mapping['name'],product_id=mapping['product_id'],quantity=base_quantity,price=unit_price,tier=mapping['price_tier'])
   if mapping['kind']!='stock' or unit_price<=0:issues.append('Verify sellable stock and price for '+mapping['name'])
   if quoted*100!=unit_price*units:issues.append('Catalogue price differs from current price for '+mapping['name'])
   available=db.execute("SELECT quantity FROM stocks WHERE product_id=? AND location='Warehouse'",(mapping['product_id'],)).fetchone()
   if not available or available[0]<base_quantity:issues.append('Insufficient warehouse stock for '+mapping['name'])
   total+=unit_price*base_quantity
  if currency!='INR':issues.append('Only INR is supported: '+rid)
  lines.append(line)
 if len({l['tier'] for l in lines})>1:issues.append('Use one price tier per order.')
 return lines,total,list(dict.fromkeys(issues))
def queue(db,shop,ident,phone,text,order_id='',catalogue=False):
 s=shop.settings(db)
 if not s['whatsapp_enabled']:return
 if catalogue:
  if not s['whatsapp_commerce_enabled'] or not s['whatsapp_catalogue_id']:return
  payload={'type':'interactive','interactive':{'type':'catalog_message','body':{'text':text},'action':{'name':'catalog_message'}}};kind='catalogue'
 else:payload={'type':'text','text':{'body':text[:4000]}};kind='order'
 shop.notification(db,ident,kind,phone,s['whatsapp_order_template'],[s['name'],order_id or 'Customer enquiry',text[:800]])
 db.execute('UPDATE notifications SET message_type=?,payload=?,order_id=? WHERE id=?',('session',json.dumps(payload),order_id,ident))
def notify(db,shop,row):
 text=f"{shop.settings(db)['name']}\nOrder {row['id']}: {row['status'].replace('_',' ')}.\nEstimated total INR {row['total']/100:.2f}."
 if row['invoice_id']:text+=' Invoice '+row['invoice_id']+' recorded.'
 if row['status']=='needs_review':text+=' Staff will check prices, products and stock before confirming.'
 elif row['status']=='new':text+=' We received your cart. Staff will confirm availability and payment; no stock is reserved yet.'
 if row['contact_allowed']:queue(db,shop,'order:'+row['id']+':'+row['updated'],row['phone'],text,row['id'])
 s=shop.settings(db)
 if s['whatsapp_enabled']:
  for staff in db.execute('SELECT * FROM internal_contacts WHERE opt_in=1'):
   shop.notification(db,'trade-internal:'+row['id']+':'+row['updated']+':'+str(staff['id']),'internal',staff['phone'],s['whatsapp_internal_template'],[s['name'],'WhatsApp order',f"{row['id']} · {row['name']} · {row['status']} · INR {row['total']/100:.2f} · Warehouse"],internal_id=staff['id'])
def inbound(db,shop,message,contacts):
 mid=str(message.get('id',''))[:250];phone=whatsapp_number(message.get('from',''));now=int(dt.datetime.now(dt.timezone.utc).timestamp());timestamp=int(message.get('timestamp',now))
 if not mid or timestamp>now+300 or timestamp<0:raise ValueError('Invalid WhatsApp message identity or time.')
 name=next((str(c.get('profile',{}).get('name',''))[:100] for c in contacts if str(c.get('wa_id'))==phone),'WhatsApp customer')
 old=db.execute('SELECT * FROM whatsapp_sessions WHERE phone=?',(phone,)).fetchone();last=max(old['last_message'] if old else 0,min(timestamp,now));stopped=old['stopped'] if old else 0
 text=str(message.get('text',{}).get('body','')).strip();upper=text.upper()
 if upper in ('STOP','UNSUBSCRIBE','CANCEL','OPT OUT'):stopped=1
 # Explicit START restores service conversation only; promotional consent stays unchanged.
 if upper=='START':stopped=0
 db.execute('INSERT INTO whatsapp_sessions VALUES(?,?,?,?) ON CONFLICT(phone) DO UPDATE SET name=excluded.name,last_message=excluded.last_message,stopped=excluded.stopped',(phone,name,last,stopped))
 changed=False
 if message.get('type')=='order':
  if db.execute('SELECT 1 FROM trade_orders WHERE source_id=?',(mid,)).fetchone():return False
  raw=message['order'];catalog_id=str(raw.get('catalog_id',''))
  lines,total,issues=price_lines(db,raw,catalog_id);s=shop.settings(db)
  if catalog_id!=s['whatsapp_catalogue_id']:issues.insert(0,'Cart came from an unconfigured catalogue.')
  ident='WA-'+hashlib.sha256(mid.encode()).hexdigest()[:12].upper();ts=stamp()
  db.execute('INSERT INTO trade_orders(id,created,updated,source_id,name,phone,status,items,total,issues,raw_order,catalog_id,contact_allowed) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(ident,ts,ts,mid,name,phone,'needs_review' if issues else 'new',json.dumps(lines),total,json.dumps(issues),json.dumps(raw),catalog_id,int(not stopped)))
  row=db.execute('SELECT * FROM trade_orders WHERE id=?',(ident,)).fetchone();notify(db,shop,row);changed=True
 elif not stopped and shop.settings(db)['whatsapp_commerce_enabled']:
  if upper in ('CATALOGUE','CATALOG','MENU','SHOP','START') and shop.settings(db)['whatsapp_catalogue_reply']:queue(db,shop,'catalogue:'+mid,phone,'Browse Al Hadiya Traders, add trading products to your cart, then send your order here.',catalogue=True)
  elif upper.startswith('STATUS') or upper=='ORDERS':
   row=db.execute('SELECT * FROM trade_orders WHERE phone=? ORDER BY created DESC LIMIT 1',(phone,)).fetchone()
   queue(db,shop,'status:'+mid,phone,f"Order {row['id']}: {row['status']}. Estimated INR {row['total']/100:.2f}." if row else 'No order found for your number. Send MENU to browse.',row['id'] if row else '')
  elif upper.startswith('CANCEL WA-'):
   ident=upper.split()[1];row=db.execute('SELECT * FROM trade_orders WHERE id=? AND phone=?',(ident,phone)).fetchone()
   if row and row['status'] in ('new','needs_review','confirmed') and not row['invoice_id']:
    db.execute("UPDATE trade_orders SET status='cancelled',updated=? WHERE id=?",(stamp(),ident));notify(db,shop,db.execute('SELECT * FROM trade_orders WHERE id=?',(ident,)).fetchone());changed=True
   else:queue(db,shop,'cancel-help:'+mid,phone,'Staff must review cancellation of this order. Please contact the trading counter.',row['id'] if row else '')
  elif upper=='HELP':queue(db,shop,'help:'+mid,phone,'Send MENU to browse and order. Send STATUS to check your latest order, or CANCEL WA-<order number> to request cancellation. Send STOP to stop messages.')
 return changed

def act(shop,action,data):
 if action=='commerce_check':
  with shop.connect() as db:s=shop.settings(db)
  if not all(re.fullmatch(r'\d+',s[k]) for k in ('whatsapp_waba_id','whatsapp_phone_id','whatsapp_catalogue_id')):raise ValueError('Enter the WABA ID and owned Meta Commerce catalogue ID first.')
  linked=api(shop,s['whatsapp_waba_id']+'/product_catalogs?limit=100').get('data',[])
  if not any(str(c['id'])==s['whatsapp_catalogue_id'] for c in linked):raise ValueError('This catalogue is not linked to the WhatsApp Business Account. Connect it in WhatsApp Manager → Catalogue first.')
  api(shop,s['whatsapp_phone_id']+'/whatsapp_commerce_settings',{'is_catalog_visible':True,'is_cart_enabled':True})
  with shop.connect() as db:db.execute("UPDATE settings SET value=? WHERE key='whatsapp_catalogue_checked'",(json.dumps(stamp()),))
  return {'linked':True,'cart_enabled':True}
 with shop.lock,shop.connect() as db:
  before=shop.capture(db)
  if action=='commerce_settings':
   ident=str(data.get('catalog_id','')).strip()
   if ident and not re.fullmatch(r'\d+',ident):raise ValueError('Enter a numeric Meta catalogue ID.')
   enabled=data.get('enabled') in (True,'on');s=shop.settings(db)
   if enabled and (ident!=s['whatsapp_catalogue_id'] or not s['whatsapp_catalogue_checked']):raise ValueError('Save the catalogue ID, check its connection, then enable catalogue automation.')
   changes={'whatsapp_catalogue_id':ident,'whatsapp_commerce_enabled':enabled,'whatsapp_catalogue_reply':data.get('reply') in (True,'on'),'whatsapp_order_template':str(data.get('order_template','al_hadiya_order_update')).strip()}
   if ident!=s['whatsapp_catalogue_id']:changes['whatsapp_catalogue_checked']=''
   for k,v in changes.items():db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(v),k))
  elif action=='commerce_product':
   catalog_id=str(data.get('catalog_id','')).strip();rid=str(data.get('retailer_id','')).strip();pid=int(data['product_id']);units=int(data.get('units',1));tier=data.get('price_tier','retail')
   if not re.fullmatch(r'\d+',catalog_id) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',rid) or not 1<=units<=1000 or tier not in ('retail','wholesale'):raise ValueError('Enter catalogue/SKU, whole pack units (1–1000) and price tier.')
   p=db.execute('SELECT kind FROM products WHERE id=?',(pid,)).fetchone()
   if not p or p['kind']!='stock':raise ValueError('Choose a packaged trading product.')
   old=db.execute('SELECT id FROM commerce_products WHERE catalog_id=? AND retailer_id=?',(catalog_id,rid)).fetchone();ident=old[0] if old else secrets.randbelow(2**50)+1
   db.execute('INSERT INTO commerce_products VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET product_id=excluded.product_id,units=excluded.units,price_tier=excluded.price_tier,active=excluded.active',(ident,catalog_id,rid,pid,units,tier,int(data.get('active') in (True,'on'))))
  elif action=='trade_order_reprice':
   row=db.execute('SELECT * FROM trade_orders WHERE id=?',(str(data.get('id','')),)).fetchone()
   if not row or row['invoice_id'] or row['status'] in ('completed','cancelled'):raise ValueError('Only an open, unbilled order can be reviewed.')
   lines,total,issues=price_lines(db,json.loads(row['raw_order']),row['catalog_id'])
   db.execute('UPDATE trade_orders SET items=?,total=?,issues=?,status=?,updated=? WHERE id=?',(json.dumps(lines),total,json.dumps(issues),'needs_review' if issues else 'new',stamp(),row['id']))
  elif action=='trade_order_status':
   row=db.execute('SELECT * FROM trade_orders WHERE id=?',(str(data.get('id','')),)).fetchone();status=data.get('status')
   if not row or status not in STATUSES or status=='needs_review':raise ValueError('Choose a valid order and status.')
   if status==row['status']:return {'saved':True}
   if row['status'] in ('completed','cancelled'):raise ValueError('Closed orders cannot be reopened. Review the invoice or create a new order.')
   if row['invoice_id'] and status=='cancelled':raise ValueError('Reverse the invoice through normal accounts controls; invoiced orders cannot be cancelled here.')
   transitions={'new':('confirmed','cancelled'),'needs_review':('confirmed','cancelled'),'confirmed':('packing','cancelled'),'packing':('ready','cancelled'),'ready':('completed','cancelled')}
   if status!=row['status'] and status not in transitions.get(row['status'],()):raise ValueError('Confirm, pack, mark ready, invoice and complete the order in sequence.')
   issues=json.loads(row['issues'])
   if status=='confirmed':
    lines,total,issues=price_lines(db,json.loads(row['raw_order']),row['catalog_id'])
    if data.get('customer_confirmed_price') is True:issues=[i for i in issues if not i.startswith('Catalogue price differs')]
    if not issues:db.execute('UPDATE trade_orders SET items=?,total=?,issues=? WHERE id=?',(json.dumps(lines),total,'[]',row['id']))
   if status not in ('cancelled','new') and issues:raise ValueError('Resolve product, stock and currency issues. Revised prices require explicit customer confirmation.')
   if status=='completed' and not row['invoice_id']:raise ValueError('Complete the POS invoice before marking this order completed.')
   db.execute('UPDATE trade_orders SET status=?,updated=? WHERE id=?',(status,stamp(),row['id']))
  else:raise ValueError('Unknown WhatsApp order action.')
  shop.audit(db,action,data);shop.record_event(db,before)
  if action.startswith('trade_order_'):notify(db,shop,db.execute('SELECT * FROM trade_orders WHERE id=?',(data['id'],)).fetchone())
 return {'saved':True}
def feed(shop,origin):
 if not origin.startswith('https://'):raise ValueError('Use the hosted HTTPS catalogue to export a Meta feed.')
 with shop.connect() as db:
  s=shop.settings(db)
  if not s['catalogue_enabled']:raise ValueError('Enable public product photos in Catalogue settings first.')
  rows=db.execute("SELECT m.*,p.name,p.brand,p.price,p.wholesale_price,p.kind,c.description,c.asset_id,COALESCE(st.quantity,0) quantity FROM commerce_products m JOIN products p ON p.id=m.product_id JOIN catalogue_products c ON c.product_id=p.id LEFT JOIN stocks st ON st.product_id=p.id AND st.location='Warehouse' WHERE m.active=1 AND m.catalog_id=? AND c.published=1 AND p.kind='stock' AND p.price>0",(s['whatsapp_catalogue_id'],)).fetchall()
 out=io.StringIO();writer=csv.writer(out);writer.writerow(['id','title','description','availability','condition','price','link','image_link','brand'])
 for r in rows:
  price=(r['wholesale_price'] if r['price_tier']=='wholesale' and r['wholesale_price']>0 else r['price'])*r['units']
  writer.writerow([r['retailer_id'],r['name']+(f" · pack of {r['units']}" if r['units']>1 else ''),r['description'] or r['name'],'in stock' if r['quantity']>=r['units'] else 'out of stock','new',f'{price/100:.2f} INR',origin+'/catalogue',origin+'/media/'+r['asset_id'],r['brand'] or s['name']])
 return out.getvalue()
