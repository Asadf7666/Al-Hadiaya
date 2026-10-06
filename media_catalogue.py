"""Local image library and a deliberately published customer catalogue."""
import base64,datetime as dt,hashlib,json,re,secrets,struct,urllib.request,urllib.error
from pathlib import Path
from notifications import read_token,whatsapp_number

def migrate(db):
 db.executescript('''
 CREATE TABLE IF NOT EXISTS media_assets(id TEXT PRIMARY KEY,name TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,created TEXT NOT NULL,meta_id TEXT NOT NULL DEFAULT '',meta_phone TEXT NOT NULL DEFAULT '',uploaded TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS catalogue_products(product_id INTEGER PRIMARY KEY REFERENCES products(id),asset_id TEXT NOT NULL REFERENCES media_assets(id),description TEXT NOT NULL DEFAULT '',published INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS catalogue_orders(id TEXT PRIMARY KEY,created TEXT NOT NULL,name TEXT NOT NULL,phone TEXT NOT NULL,items TEXT NOT NULL,total INTEGER NOT NULL,note TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'new');
 ''')
 for table,columns in [('whatsapp_campaigns',[('asset_id',"TEXT NOT NULL DEFAULT ''")]),('notifications',[('image_id',"TEXT NOT NULL DEFAULT ''")]),('whatsapp_templates',[('header_format',"TEXT NOT NULL DEFAULT ''"),('parameter_count','INTEGER NOT NULL DEFAULT 3'),('components',"TEXT NOT NULL DEFAULT '[]'")])]:
  existing={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
  for key,kind in columns:
   if key not in existing:db.execute('ALTER TABLE '+table+' ADD COLUMN '+key+' '+kind)
 if 'request_key' not in {r[1] for r in db.execute('PRAGMA table_info(catalogue_orders)')}:db.execute("ALTER TABLE catalogue_orders ADD COLUMN request_key TEXT NOT NULL DEFAULT ''")
 db.execute("CREATE UNIQUE INDEX IF NOT EXISTS catalogue_request_unique ON catalogue_orders(request_key) WHERE request_key<>''")
 for key,value in {'catalogue_enabled':False,'catalogue_phone':'','catalogue_banner':''}.items():db.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(key,json.dumps(value)))

def state(db):
 return {k:[dict(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY rowid DESC LIMIT 100')] for k,table in [('media_assets','media_assets'),('catalogue_products','catalogue_products'),('catalogue_orders','catalogue_orders')]}

def image_info(raw):
 if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw)>32 and raw[12:16]==b'IHDR':
  w,h=struct.unpack('>II',raw[16:24]);mime='image/png'
 elif raw.startswith(b'\xff\xd8'):
  pos=2;w=h=0;mime='image/jpeg'
  while pos+4<len(raw):
   if raw[pos]!=255:raise ValueError('Invalid JPEG image.')
   while pos<len(raw) and raw[pos]==255:pos+=1
   if pos>=len(raw):raise ValueError('Invalid JPEG image.')
   marker=raw[pos];pos+=1
   if marker in (0xd9,0xda):break
   if marker in range(0xd0,0xd8):continue
   length=int.from_bytes(raw[pos:pos+2],'big')
   if length<2 or pos+length>len(raw):raise ValueError('Invalid JPEG image.')
   if marker in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
    if length<8:raise ValueError('Invalid JPEG image.')
    h,w=struct.unpack('>HH',raw[pos+3:pos+7]);break
   pos+=length
 else:raise ValueError('Upload a JPEG or PNG image.')
 if not w or not h or w>4096 or h>4096 or w*h>12000000:raise ValueError('Use an image under 4096 pixels per side and 12 megapixels.')
 return mime

def asset_path(shop,ident):
 if not re.fullmatch(r'[a-f0-9]{64}',str(ident)):raise ValueError('Invalid image identifier.')
 return shop.folder/'media'/ident

def upload(shop,data):
 try:raw=base64.b64decode(str(data.get('content','')),validate=True)
 except Exception:raise ValueError('Invalid image upload.') from None
 if not raw or len(raw)>5000000:raise ValueError('Upload an image of up to 5 MB.')
 mime=image_info(raw);ident=hashlib.sha256(raw).hexdigest();name=Path(str(data.get('name','Image'))).name[:100]
 folder=shop.folder/'media';folder.mkdir(exist_ok=True)
 path=asset_path(shop,ident)
 if not path.exists():
  try:
   with path.open('xb') as f:f.write(raw)
  except FileExistsError:pass
 with shop.lock,shop.connect() as db:
  db.execute('INSERT OR IGNORE INTO media_assets(id,name,mime,size,created) VALUES(?,?,?,?,?)',(ident,name,mime,len(raw),dt.datetime.now(dt.timezone.utc).isoformat()))
  shop.audit(db,'media_upload',{'id':ident,'name':name})
 return {'id':ident,'mime':mime}

def meta_image(shop,ident,db):
 asset=db.execute('SELECT * FROM media_assets WHERE id=?',(ident,)).fetchone()
 if not asset:raise ValueError('Select an uploaded image.')
 settings=shop.settings(db);phone=settings['whatsapp_phone_id'];token=read_token(shop.folder)
 if asset['meta_id'] and asset['meta_phone']==phone and dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(asset['uploaded'])<dt.timedelta(days=27):return asset['meta_id']
 if not token or not re.fullmatch(r'\d+',phone) or not re.fullmatch(r'v\d+\.\d+',settings['whatsapp_api_version']):raise ValueError('Configure the WhatsApp sender before uploading an image to Meta.')
 raw=asset_path(shop,ident).read_bytes();boundary='alhidaya-'+secrets.token_hex(12)
 ext='.png' if asset['mime']=='image/png' else '.jpg'
 body=(('--'+boundary+'\r\nContent-Disposition: form-data; name="messaging_product"\r\n\r\nwhatsapp\r\n--'+boundary+'\r\nContent-Disposition: form-data; name="type"\r\n\r\n'+asset['mime']+'\r\n--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="image'+ext+'"\r\nContent-Type: '+asset['mime']+'\r\n\r\n').encode()+raw+('\r\n--'+boundary+'--\r\n').encode())
 req=urllib.request.Request('https://graph.facebook.com/'+settings['whatsapp_api_version']+'/'+phone+'/media',data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'multipart/form-data; boundary='+boundary})
 try:
  with urllib.request.urlopen(req,timeout=25) as response:result=json.load(response)
 except (urllib.error.URLError,OSError,TimeoutError):raise ValueError('Meta image upload failed. Check sender access and connectivity; campaign remains a draft.') from None
 if not result.get('id'):raise ValueError('Meta did not return an image ID.')
 db.execute('UPDATE media_assets SET meta_id=?,meta_phone=?,uploaded=? WHERE id=?',(result['id'],phone,dt.datetime.now(dt.timezone.utc).isoformat(),ident))
 return result['id']

def act(shop,action,data):
 if action=='media_upload':return upload(shop,data)
 with shop.lock,shop.connect() as db:
  if action=='catalogue_product':
   pid=int(data['product_id']);p=db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone();asset=str(data.get('asset_id',''))
   if not p or p['kind']=='ingredient':raise ValueError('Choose a sellable product.')
   if not db.execute('SELECT 1 FROM media_assets WHERE id=?',(asset,)).fetchone():raise ValueError('Upload and select a product photo.')
   published=data.get('published') in (True,1,'on','true')
   if published and p['price']<=0:raise ValueError('Set a retail price before publishing this product.')
   description=str(data.get('description','')).strip()
   if len(description)>500:raise ValueError('Description must be under 500 characters.')
   if published:__import__('whatsapp_policy').approve_catalogue(db,p,asset,description,data.get('policy_confirmed'))
   db.execute('INSERT INTO catalogue_products VALUES(?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET asset_id=excluded.asset_id,description=excluded.description,published=excluded.published',(pid,asset,description,int(published)))
  elif action=='catalogue_settings':
   phone=whatsapp_number(data['phone']) if str(data.get('phone','')).strip() else ''
   banner=str(data.get('banner','')).strip()
   if banner and not db.execute('SELECT 1 FROM media_assets WHERE id=?',(banner,)).fetchone():raise ValueError('Select an uploaded banner image.')
   for k,v in {'catalogue_enabled':data.get('enabled') in (True,1,'on','true'),'catalogue_phone':phone,'catalogue_banner':banner}.items():db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(v),k))
  elif action=='catalogue_order_status':
   status=str(data.get('status',''))
   if status not in ('new','contacted','fulfilled','cancelled'):raise ValueError('Choose a valid order status.')
   if not db.execute('SELECT 1 FROM catalogue_orders WHERE id=?',(str(data.get('id','')),)).fetchone():raise ValueError('Order request not found.')
   db.execute('UPDATE catalogue_orders SET status=? WHERE id=?',(status,data['id']))
  else:raise ValueError('Unknown catalogue action.')
  shop.audit(db,action,{k:v for k,v in data.items() if k!='content'})
 return {'saved':True}

def public_state(shop):
 with shop.lock,shop.connect() as db:
  settings=shop.settings(db)
  if not settings['catalogue_enabled']:return {'name':settings['name'],'enabled':False,'products':[],'phone':'','banner':''}
  rows=db.execute("SELECT p.id,p.name,p.price,p.category,p.unit,p.size,p.brand,p.kind,p.stock,c.asset_id,c.description FROM catalogue_products c JOIN products p ON p.id=c.product_id WHERE c.published=1 AND p.price>0 AND p.kind<>'ingredient'")
  products=[{k:r[k] for k in ('id','name','price','category','unit','size','brand','kind','asset_id','description')}|{'available':r['stock']>0 or r['kind']=='recipe'} for r in rows if __import__('whatsapp_policy').catalogue_ready(db,r,r['asset_id'],r['description'])]
  return {'name':settings['name'],'enabled':True,'products':products,'phone':settings['catalogue_phone'],'banner':settings['catalogue_banner']}

def public_asset(shop,ident):
 with shop.connect() as db:
  settings=shop.settings(db)
  return settings['catalogue_enabled'] and (settings['catalogue_banner']==ident or any(p['asset_id']==ident for p in public_state(shop)['products']))

def order(shop,data):
 with shop.lock,shop.connect() as db:
  request_key=str(data.get('request_key',''))
  if not re.fullmatch(r'[a-f0-9]{32}',request_key):raise ValueError('Invalid order request identifier.')
  old=db.execute('SELECT id,total FROM catalogue_orders WHERE request_key=?',(request_key,)).fetchone()
  if old:return {'id':old['id'],'total':old['total'],'message':'This order request was already received.'}
  name=str(data.get('name','')).strip();phone=whatsapp_number(data.get('phone',''));note=str(data.get('note','')).strip()
  if not name or len(name)>100 or len(note)>500 or data.get('contact_consent') is not True:raise ValueError('Enter your name and agree to be contacted about this order.')
  items=data.get('items',[])
  if not isinstance(items,list) or not items or len(items)>30:raise ValueError('Select between 1 and 30 products.')
  catalogue=public_state(shop)
  if not catalogue['enabled']:raise ValueError('The catalogue is currently unavailable.')
  products={p['id']:p for p in catalogue['products']};seen=set();lines=[];total=0
  for item in items:
   if not isinstance(item,dict):raise ValueError('Invalid catalogue selection.')
   pid=int(item['id']);quantity=int(item['quantity'])
   if isinstance(item['quantity'],bool) or quantity!=item['quantity']:raise ValueError('Use whole quantities for catalogue orders.')
   if pid in seen or pid not in products or quantity<1 or quantity>100:raise ValueError('Invalid catalogue selection.')
   p=products[pid]
   if not p['available']:raise ValueError('An item is currently unavailable. Refresh the catalogue.')
   seen.add(pid);lines.append({'id':pid,'name':p['name'],'quantity':quantity,'price':p['price']});total+=p['price']*quantity
  ident='REQ-'+secrets.token_hex(6).upper()
  db.execute('INSERT INTO catalogue_orders(id,created,name,phone,items,total,note,request_key) VALUES(?,?,?,?,?,?,?,?)',(ident,dt.datetime.now(dt.timezone.utc).isoformat(),name,phone,json.dumps(lines),total,note,request_key))
  return {'id':ident,'total':total,'message':'Order request saved. The shop will confirm availability and payment. This is not an invoice or a payment.'}
