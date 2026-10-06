"""Al Hadiya Traders — offline, single-PC shop management. Python standard library."""
import argparse
import datetime as dt
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
import webbrowser
from decimal import Decimal, ROUND_HALF_UP, DecimalException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
sys.path.insert(0,str(ROOT))
DATA = Path(os.environ.get('AL_HIDAYA_DATA', str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'AlHidayaTraders')))
TOKEN = secrets.token_urlsafe(32)

def now():
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')

def money(value):
    d = Decimal(str(value))
    if not d.is_finite() or d < 0:
        raise ValueError('Amount must be a finite positive number or zero.')
    return int((d * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def number(value, positive=False):
    d = float(value)
    if not __import__('math').isfinite(d) or d < 0 or (positive and d <= 0):
        raise ValueError('Enter a valid positive quantity.')
    return d

def required(value, label='Name'):
    value = str(value or '').strip()
    if not value:
        raise ValueError(label + ' is required.')
    return value

class ClosingConnection(sqlite3.Connection):
    """Commit/rollback a context and release Windows file handles immediately."""
    def __exit__(self,*args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

SCHEMA = '''

                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,sku TEXT UNIQUE NOT NULL,
                  category TEXT NOT NULL,unit TEXT NOT NULL,price INTEGER NOT NULL,cost INTEGER NOT NULL,
                  gst REAL NOT NULL DEFAULT 0,cess REAL NOT NULL DEFAULT 0,hsn TEXT DEFAULT '',stock REAL NOT NULL DEFAULT 0,
                  minimum REAL NOT NULL DEFAULT 5,pack REAL NOT NULL DEFAULT 1,expiry TEXT DEFAULT '',kind TEXT NOT NULL DEFAULT 'stock');
                CREATE TABLE IF NOT EXISTS recipes(product_id INTEGER REFERENCES products(id),ingredient_id INTEGER REFERENCES products(id),
                  quantity REAL NOT NULL,PRIMARY KEY(product_id,ingredient_id));
                CREATE TABLE IF NOT EXISTS parties(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT DEFAULT '',
                  kind TEXT NOT NULL,gstin TEXT DEFAULT '',address TEXT DEFAULT '',balance INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,kind TEXT NOT NULL,date TEXT NOT NULL,
                  party_id INTEGER REFERENCES parties(id),total INTEGER NOT NULL,tax INTEGER NOT NULL,paid INTEGER NOT NULL,
                  payment TEXT NOT NULL,discount INTEGER NOT NULL DEFAULT 0,reference TEXT DEFAULT '',reversed INTEGER DEFAULT 0,snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lines(id INTEGER PRIMARY KEY,document_id TEXT REFERENCES documents(id),
                  product_id INTEGER REFERENCES products(id),name TEXT NOT NULL,quantity REAL NOT NULL,price INTEGER NOT NULL,
                  total INTEGER NOT NULL,tax INTEGER NOT NULL,cost INTEGER NOT NULL,gst REAL NOT NULL,cess REAL NOT NULL,hsn TEXT DEFAULT '');
                CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY,date TEXT NOT NULL,product_id INTEGER REFERENCES products(id),
                  quantity REAL NOT NULL,reference TEXT NOT NULL,note TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY,date TEXT NOT NULL,party_id INTEGER REFERENCES parties(id),
                  amount INTEGER NOT NULL,method TEXT NOT NULL,note TEXT DEFAULT '');
                CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY,date TEXT NOT NULL,name TEXT NOT NULL,
                  amount INTEGER NOT NULL,method TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,date TEXT NOT NULL,action TEXT NOT NULL,details TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS stocks(product_id INTEGER REFERENCES products(id),location TEXT NOT NULL,quantity REAL NOT NULL DEFAULT 0,
                  PRIMARY KEY(product_id,location));
                CREATE TABLE IF NOT EXISTS sync_events(id TEXT PRIMARY KEY,date TEXT NOT NULL,device TEXT NOT NULL,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sync_seen(id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS sync_versions(entity TEXT PRIMARY KEY,version TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sync_errors(id TEXT PRIMARY KEY,message TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT NOT NULL,location TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS allocations(device_id TEXT REFERENCES devices(id),product_id INTEGER REFERENCES products(id),
                  location TEXT NOT NULL,quantity REAL NOT NULL DEFAULT 0,PRIMARY KEY(device_id,product_id,location));
                CREATE TABLE IF NOT EXISTS internal_contacts(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,opt_in INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,created TEXT NOT NULL,kind TEXT NOT NULL,
                  party_id INTEGER REFERENCES parties(id),phone TEXT NOT NULL,template TEXT NOT NULL,parameters TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'queued',attempts INTEGER NOT NULL DEFAULT 0,next_attempt TEXT NOT NULL,
                  detail TEXT DEFAULT '',provider_id TEXT DEFAULT '',internal_id INTEGER REFERENCES internal_contacts(id));
            '''

class Shop:
    def __init__(self, folder=DATA):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'shop.sqlite3'
        self.lock = threading.RLock()
        self.cloud_lock = threading.RLock()
        with self.connect() as db:
            db.executescript('PRAGMA journal_mode=WAL;' + SCHEMA)
            defaults = {'name':'Al Hadiya Traders','address':'','phone':'','gstin':'','state':'29','gst_enabled':False,
                        'invoice_prefix':'AH','backup_folder':'','last_backup':'','printer':'80','demo':False,
                        'device_id':secrets.token_hex(8),'device_location':'','sync_folder':'','last_sync':'',
                        'admin_device_id':'','device_name':'','setup_role':'owner',
                        'cloud_url':'','cloud_business_id':'','cloud_cursor':0,'node_mode':'unified',
                        'whatsapp_enabled':False,'whatsapp_phone_id':'','whatsapp_api_version':'','whatsapp_language':'en',
                        'whatsapp_invoice_template':'','whatsapp_payment_template':'','whatsapp_internal_template':'',
                        'whatsapp_waba_id':'','whatsapp_timezone':'Asia/Kolkata','whatsapp_daily_time':'','whatsapp_low_stock':True,'whatsapp_transfers':True,'whatsapp_purchases':True,'whatsapp_sales':False,'whatsapp_payments':False,'whatsapp_expenses':False,'whatsapp_reversals':True,'whatsapp_profiles':True,'whatsapp_catalogue':True,'whatsapp_stock':True,'whatsapp_recipes':True,'whatsapp_orders':True}
            for k,v in defaults.items():
                db.execute('INSERT OR IGNORE INTO settings VALUES(?,?)', (k,json.dumps(v)))
            for table in ('documents','movements'):
                if 'location' not in {r[1] for r in db.execute('PRAGMA table_info('+table+')')}:
                    db.execute('ALTER TABLE '+table+" ADD COLUMN location TEXT NOT NULL DEFAULT 'Outlet'")
            if 'barcode' not in {r[1] for r in db.execute('PRAGMA table_info(products)')}:
                db.execute("ALTER TABLE products ADD COLUMN barcode TEXT NOT NULL DEFAULT ''")
            if 'tax_verified' not in {r[1] for r in db.execute('PRAGMA table_info(products)')}:
                db.execute('ALTER TABLE products ADD COLUMN tax_verified INTEGER NOT NULL DEFAULT 0')
            for key,kind,default in [('brand','TEXT',"''"),('size','TEXT',"''"),('packaging','TEXT',"''"),('mrp','INTEGER','0'),('wholesale_price','INTEGER','0')]:
                if key not in {r[1] for r in db.execute('PRAGMA table_info(products)')}:
                    db.execute('ALTER TABLE products ADD COLUMN '+key+' '+kind+' NOT NULL DEFAULT '+default)
            for key,kind,default in [('email','TEXT',"''"),('notes','TEXT',"''"),('price_tier','TEXT',"'retail'"),('credit_limit','INTEGER','0'),('whatsapp_opt_in','INTEGER','0'),('whatsapp_marketing_opt_in','INTEGER','0'),('whatsapp_consent_date','TEXT',"''")]:
                if key not in {r[1] for r in db.execute('PRAGMA table_info(parties)')}:
                    db.execute('ALTER TABLE parties ADD COLUMN '+key+' '+kind+' NOT NULL DEFAULT '+default)
            from outreach import migrate
            migrate(db)
            __import__("procurement").migrate(db)
            db.execute("UPDATE notifications SET status='uncertain',detail='App restarted during a send. Check Meta before trying again.' WHERE status='sending'")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS barcode_unique ON products(barcode) WHERE barcode<>''")
            for p in db.execute('SELECT id,stock FROM products'):
                if not db.execute('SELECT 1 FROM stocks WHERE product_id=?',(p['id'],)).fetchone():
                    db.execute('INSERT INTO stocks VALUES(?,?,?)',(p['id'],'Outlet',p['stock']))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def settings(self, db):
        return {r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM settings')}

    def audit(self, db, action, details):
        db.execute('INSERT INTO audit(date,action,details) VALUES(?,?,?)', (now(),action,json.dumps(details)))

    def state(self):
        with self.lock, self.connect() as db:
            result = {table:[dict(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY rowid DESC')] for table in
                      ['products','recipes','parties','documents','lines','expenses','payments','stocks','devices','allocations']}
            result['movements'] = [dict(r) for r in db.execute('SELECT * FROM movements ORDER BY id DESC LIMIT 200')]
            result['settings'] = self.settings(db)
            result['sync_errors'] = [dict(r) for r in db.execute('SELECT * FROM sync_errors')]
            for doc in result['documents']:
                doc['snapshot'] = json.loads(doc['snapshot'])
            result['local'] = True
            result['notifications'] = [dict(r) for r in db.execute('SELECT * FROM notifications ORDER BY created DESC LIMIT 100')]
            from media_catalogue import state as media_state
            result.update(media_state(db))
            from whatsapp_orders import state as order_state
            result.update(order_state(db))
            result.update(__import__('procurement').state(db))
            result['stock_alerts']=__import__('stock_alerts').alerts(db,self.settings(db))
            result['campaigns'] = [dict(r) for r in db.execute('SELECT * FROM whatsapp_campaigns ORDER BY created DESC LIMIT 100')]
            result['whatsapp_templates'] = [dict(r) for r in db.execute('SELECT * FROM whatsapp_templates ORDER BY name,language')]
            from outreach import webhook_configured
            result['whatsapp_webhook_configured'] = webhook_configured(self.folder)
            result['internal_contacts'] = [dict(r) for r in db.execute('SELECT * FROM internal_contacts ORDER BY name')]
            from notifications import token_file
            result['whatsapp_token_configured'] = token_file(self.folder).exists()
            return result

    def location(self, value):
        if value not in ('Warehouse','Outlet'):
            raise ValueError('Choose Warehouse or Outlet.')
        return value

    def movement(self, db, pid, qty, ref, note, location='Outlet'):
        self.location(location)
        p = db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
        if not p or p['kind'] == 'recipe':
            raise ValueError('Select a stocked product or ingredient.')
        db.execute('INSERT OR IGNORE INTO stocks VALUES(?,?,0)',(pid,location))
        stock = db.execute('SELECT quantity FROM stocks WHERE product_id=? AND location=?',(pid,location)).fetchone()[0]
        settings = self.settings(db)
        if settings['admin_device_id'] and settings.get('node_mode')!='unified':
            actor = settings['device_id']
            if actor == settings['admin_device_id']:
                reserved = db.execute('SELECT COALESCE(SUM(quantity),0) FROM allocations WHERE product_id=? AND location=?',(pid,location)).fetchone()[0]
                if qty < 0 and stock-reserved+qty < -0.000001:
                    raise ValueError('Stock is allocated to another PC. Sell or transfer only unallocated stock from this counter.')
            else:
                db.execute('INSERT OR IGNORE INTO allocations VALUES(?,?,?,0)',(actor,pid,location))
                allowance = db.execute('SELECT quantity FROM allocations WHERE device_id=? AND product_id=? AND location=?',(actor,pid,location)).fetchone()[0]
                if allowance+qty < -0.000001:
                    raise ValueError('This PC’s stock allowance is insufficient. Ask the main warehouse PC to allocate stock, then sync.')
                db.execute('UPDATE allocations SET quantity=ROUND(quantity+?,6) WHERE device_id=? AND product_id=? AND location=?',(qty,actor,pid,location))
        if stock + qty < -0.000001:
            raise ValueError('Insufficient stock in '+location+': '+p['name'])
        db.execute('UPDATE stocks SET quantity=ROUND(quantity+?,6) WHERE product_id=? AND location=?',(qty,pid,location))
        db.execute('UPDATE products SET stock=ROUND(stock+?,6) WHERE id=?',(qty,pid))
        db.execute('INSERT INTO movements(date,product_id,quantity,reference,note,location) VALUES(?,?,?,?,?,?)',(now(),pid,qty,ref,note,location))

    def act(self, action, data):
        if action == 'cloud_address':
            from cloud_sync import change_server
            return change_server(self,data)
        if action == 'cloud_pair':
            from cloud_sync import pair_desktop
            return pair_desktop(self,data)
        if action == 'backup':
            return self.backup()
        if action == 'sync':
            return self.sync()
        if action in ('inventory_plan','purchase_order_create','purchase_order_status'):
            return __import__('procurement').act(self,action,data)
        if action in ('commerce_settings','commerce_check','commerce_product','trade_order_status','trade_order_reprice'):
            from whatsapp_orders import act
            return act(self,action,data)
        if action in ('media_upload','catalogue_product','catalogue_settings','catalogue_order_status'):
            from media_catalogue import act
            return act(self,action,data)
        if action in ('campaign_create','campaign_approve','campaign_cancel','whatsapp_templates','whatsapp_webhook'):
            from outreach import act
            return act(self,action,data)
        if action == 'whatsapp_send':
            from notifications import process_outbox
            return process_outbox(self)
        with self.lock, self.connect() as db:
            before = self.capture(db)
            device_location = self.settings(db)['device_location']
            configuration = self.settings(db)
            admin = configuration['admin_device_id']
            is_admin = configuration.get('node_mode')=='unified' or not device_location or (admin and admin == configuration['device_id'])
            result = {}
            if action == 'product':
                result = self.save_product(db,data)
            elif action == 'catalog':
                result = self.load_catalog(db)
            elif action == 'import_products':
                rows = data.get('rows',[])
                if not rows or len(rows) > 1000:
                    raise ValueError('Import between 1 and 1,000 product rows at a time.')
                for row in rows:
                    existing = db.execute('SELECT * FROM products WHERE sku=?',(row.get('sku'),)).fetchone()
                    row = dict(row)
                    opening = number(row.get('opening_stock') or 0)
                    if existing and opening:
                        raise ValueError('Opening stock is only allowed for new products. Adjust existing stock separately.')
                    if existing:
                        merged = dict(existing)
                        for key in ('price','cost','mrp','wholesale_price'):
                            merged[key] = Decimal(merged[key])/100
                        merged.update(row)
                        row = merged
                    row['id'] = existing['id'] if existing else None
                    row['stock'] = opening
                    self.save_product(db,row)
                result = {'count':len(rows)}
            elif action == 'party':
                kind = data.get('kind')
                if kind not in ('customer','supplier'):
                    raise ValueError('Invalid party type.')
                pid = data.get('id')
                existing = db.execute('SELECT * FROM parties WHERE id=?',(pid,)).fetchone() if pid else None
                if pid and not existing:
                    raise ValueError('Customer or supplier not found.')
                if existing and existing['kind'] != kind:
                    raise ValueError('A customer cannot be converted to a supplier. Create a separate supplier profile.')
                tier = data.get('price_tier','retail')
                if tier not in ('retail','wholesale'):
                    raise ValueError('Select retail or wholesale pricing.')
                limit = money(data.get('credit_limit',0))
                if not is_admin and (limit != (existing['credit_limit'] if existing else 0)):
                    raise ValueError('Credit limits are managed on the main PC.')
                values = (required(data.get('name')),str(data.get('phone','')),kind,str(data.get('gstin','')).strip().upper(),
                          str(data.get('address','')),str(data.get('email','')),str(data.get('notes','')),tier,limit)
                if existing:
                    db.execute('UPDATE parties SET name=?,phone=?,kind=?,gstin=?,address=?,email=?,notes=?,price_tier=?,credit_limit=? WHERE id=?',values+(pid,))
                else:
                    pid = secrets.randbelow(2**50)+1
                    db.execute('INSERT INTO parties(name,phone,kind,gstin,address,email,notes,price_tier,credit_limit,id) VALUES(?,?,?,?,?,?,?,?,?,?)',values+(pid,))
                opted_in = data.get('whatsapp_opt_in') in (True,1,'1','on','true')
                if opted_in:
                    from notifications import whatsapp_number
                    whatsapp_number(data.get('phone'))
                marketing = data.get('whatsapp_marketing_opt_in') in (True,1,'1','on','true')
                if marketing:
                    from notifications import whatsapp_number
                    whatsapp_number(data.get('phone'))
                consent_date = existing['whatsapp_consent_date'] if existing else ''
                if marketing and (not existing or not existing['whatsapp_marketing_opt_in'] or existing['phone']!=str(data.get('phone',''))):
                    consent_date = now()
                db.execute('UPDATE parties SET whatsapp_opt_in=?,whatsapp_marketing_opt_in=?,whatsapp_consent_date=? WHERE id=?',(int(opted_in),int(marketing),consent_date,pid))
                result = {'id':pid}
            elif action == 'recipe':
                pid = int(data['product_id'])
                p = db.execute('SELECT kind FROM products WHERE id=?',(pid,)).fetchone()
                if not p or p['kind'] != 'recipe':
                    raise ValueError('Select a café recipe product.')
                items = data.get('items',[])
                if not items:
                    raise ValueError('Add at least one ingredient.')
                db.execute('DELETE FROM recipes WHERE product_id=?',(pid,))
                for item in items:
                    iid = int(item['ingredient_id'])
                    ingredient = db.execute('SELECT kind FROM products WHERE id=?',(iid,)).fetchone()
                    if not ingredient or ingredient['kind'] != 'ingredient':
                        raise ValueError('Recipe components must be ingredients.')
                    db.execute('INSERT INTO recipes VALUES(?,?,?)',(pid,iid,number(item['quantity'],True)))
            elif action in ('sale','purchase'):
                result = self.document(db,action,data)
            elif action == 'adjust':
                qty = float(data['quantity'])
                if not __import__('math').isfinite(qty) or qty == 0:
                    raise ValueError('Adjustment quantity must be non-zero.')
                self.movement(db,int(data['product_id']),qty,'ADJUST',required(data.get('note'),'Reason'),data.get('location','Outlet'))
            elif action == 'transfer':
                source = self.location(data['source'])
                target = self.location(data['target'])
                if source == target:
                    raise ValueError('Choose different source and destination locations.')
                pid = int(data['product_id'])
                qty = number(data['quantity'],True)
                ref = 'TR-'+secrets.token_hex(5).upper()
                note = str(data.get('note','Stock transfer'))
                self.movement(db,pid,-qty,ref,note,source)
                self.movement(db,pid,qty,ref,note,target)
                result = {'id':ref}
            elif action == 'allocate':
                if configuration.get('node_mode')=='unified':
                    raise ValueError('Stock is shared across all nodes; PC allocations are no longer used.')
                if not is_admin or not admin:
                    raise ValueError('Stock allocation is unavailable.')
                target = required(data.get('device_id'),'Target PC')
                device = db.execute('SELECT * FROM devices WHERE id=?',(target,)).fetchone()
                if not device or target == admin:
                    raise ValueError('Choose a registered additional PC. The main PC uses unallocated stock.')
                pid = int(data['product_id'])
                p = db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
                if not p or p['kind'] == 'recipe':
                    raise ValueError('Allocate packaged stock or café ingredients, not recipe products.')
                quantity = number(data['quantity'],True)
                loc = device['location']
                stockrow = db.execute('SELECT quantity FROM stocks WHERE product_id=? AND location=?',(pid,loc)).fetchone()
                available = (stockrow[0] if stockrow else 0)-db.execute('SELECT COALESCE(SUM(quantity),0) FROM allocations WHERE product_id=? AND location=?',(pid,loc)).fetchone()[0]
                if quantity > available+0.000001:
                    raise ValueError('Not enough unallocated stock at '+loc+'. Transfer or receive stock first.')
                db.execute('INSERT OR IGNORE INTO allocations VALUES(?,?,?,0)',(target,pid,loc))
                db.execute('UPDATE allocations SET quantity=ROUND(quantity+?,6) WHERE device_id=? AND product_id=? AND location=?',(quantity,target,pid,loc))
                result = {'allocated':quantity,'device':device['name'],'location':loc}
            elif action == 'release_allocation':
                actor = configuration['device_id']
                pid = int(data['product_id'])
                quantity = number(data['quantity'],True)
                row = db.execute('SELECT quantity FROM allocations WHERE device_id=? AND product_id=? AND location=?',(actor,pid,device_location)).fetchone()
                if not row or quantity > row[0]:
                    raise ValueError('Release no more than this PC’s unused stock allowance.')
                db.execute('UPDATE allocations SET quantity=ROUND(quantity-?,6) WHERE device_id=? AND product_id=? AND location=?',(quantity,actor,pid,device_location))
            elif action == 'payment':
                pid = int(data['party_id'])
                p = db.execute('SELECT * FROM parties WHERE id=?',(pid,)).fetchone()
                amount = money(data['amount'])
                if not p or amount <= 0 or amount > p['balance']:
                    raise ValueError('Payment must be greater than zero and no more than the outstanding balance.')
                method = self.method(data.get('method'))
                db.execute('INSERT INTO payments(date,party_id,amount,method,note) VALUES(?,?,?,?,?)',(now(),pid,amount,method,str(data.get('note',''))))
                db.execute('UPDATE parties SET balance=balance-? WHERE id=?',(amount,pid))
            elif action == 'expense':
                amount = money(data['amount'])
                if amount <= 0:
                    raise ValueError('Expense must be greater than zero.')
                db.execute('INSERT INTO expenses(date,name,amount,method) VALUES(?,?,?,?)',(now(),required(data.get('name')),amount,self.method(data.get('method'))))
            elif action == 'whatsapp_settings':
                import re
                enabled = bool(data.get('whatsapp_enabled'))
                for key in ('whatsapp_phone_id','whatsapp_api_version','whatsapp_language','whatsapp_invoice_template','whatsapp_payment_template','whatsapp_internal_template','whatsapp_daily_time','whatsapp_waba_id','whatsapp_timezone'):
                    value = str(data.get(key,self.settings(db).get(key,''))).strip()
                    if key in ('whatsapp_invoice_template','whatsapp_payment_template','whatsapp_internal_template') and value and not re.fullmatch(r'[a-z0-9_]{1,512}',value):
                        raise ValueError('Template names must match your approved WhatsApp templates.')
                    if key == 'whatsapp_timezone':
                        if value not in ('Asia/Kolkata','UTC'):raise ValueError('Choose Asia/Kolkata or UTC for notification scheduling.')
                    if key == 'whatsapp_waba_id' and value and not re.fullmatch(r'[0-9]+',value):raise ValueError('Enter a numeric WhatsApp Business Account ID.')
                    if key == 'whatsapp_daily_time' and value:
                        dt.time.fromisoformat(value)
                    db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(value),key))
                for key in ('whatsapp_enabled','whatsapp_low_stock','whatsapp_transfers','whatsapp_purchases','whatsapp_sales','whatsapp_payments','whatsapp_expenses','whatsapp_reversals','whatsapp_profiles','whatsapp_catalogue','whatsapp_stock','whatsapp_recipes','whatsapp_orders'):
                    db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(bool(data.get(key,self.settings(db).get(key,False)))),key))
                if enabled:
                    configured = self.settings(db)
                    if not re.fullmatch(r'[0-9]+',configured['whatsapp_phone_id']) or not re.fullmatch(r'v[0-9]+\.[0-9]+',configured['whatsapp_api_version']):
                        raise ValueError('Enter your Meta sender phone-number ID and a supported Graph API version.')
                if data.get('token'):
                    from notifications import save_token
                    save_token(self.folder,data['token'])
            elif action == 'internal_contact':
                from notifications import whatsapp_number
                phone = whatsapp_number(data.get('phone'))
                opted_in = data.get('opt_in') in (True,1,'1','on','true')
                if data.get('id'):
                    db.execute('UPDATE internal_contacts SET name=?,phone=?,opt_in=? WHERE id=?',(required(data.get('name')),phone,int(opted_in),int(data['id'])))
                else:
                    db.execute('INSERT INTO internal_contacts(name,phone,opt_in) VALUES(?,?,?)',(required(data.get('name')),phone,int(opted_in)))
            elif action == 'reverse':
                result = self.reverse(db,data)
            elif action == 'settings':
                if configuration.get('cloud_url') and data.get('sync_folder'):
                    raise ValueError('This PC uses authenticated server sync. Do not also enable folder sync.')
                if not is_admin and admin:
                    shared = ('name','address','phone','gstin','state','gst_enabled','invoice_prefix')
                    for key in shared:
                        if key in data and data[key] != configuration[key]:
                            raise ValueError('Business and GST settings are managed on the main warehouse PC.')
                for k in ('name','address','phone','gstin','state','gst_enabled','invoice_prefix','backup_folder','printer','sync_folder','device_location','device_name','setup_role'):
                    if k in data:
                        v = data[k]
                        if k in ('name','invoice_prefix'):
                            v = required(v,k)
                        if k == 'invoice_prefix':
                            import re
                            if not re.fullmatch(r'[A-Z0-9]{1,2}',v):
                                raise ValueError('Invoice prefix must be 1–2 uppercase letters or digits (keeps invoice numbers within 16 characters).')
                        if k == 'gst_enabled':
                            v = bool(v)
                            if v:
                                import re
                                gstin = str(data.get('gstin','')).upper()
                                if not re.fullmatch(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]',gstin) or gstin[:2] != str(data.get('state')):
                                    raise ValueError('Enter a GSTIN matching your state code before enabling GST. Verify registration and rates with your accountant.')
                        if k == 'device_location' and v:
                            self.location(v)
                            old = self.settings(db)['device_location']
                            if configuration.get('node_mode')!='unified' and old and old != v and db.execute('SELECT 1 FROM documents LIMIT 1').fetchone():
                                raise ValueError('Device location cannot change after billing starts.')
                        db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(v),k))
                updated = self.settings(db)
                if updated['device_location']:
                    role = updated['setup_role']
                    if role not in ('owner','join'):
                        raise ValueError('Choose first/main PC or joining PC.')
                    if not admin and updated['device_location'] == 'Warehouse' and role == 'owner':
                        if updated.get('node_mode')!='unified':db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(updated['device_id']),'admin_device_id'))
                        if not db.execute('SELECT 1 FROM products').fetchone():
                            result = self.load_catalog(db)
                    name = updated['device_name'].strip() or updated['device_location']+' '+updated['device_id'][:6].upper()
                    db.execute('INSERT INTO devices(id,name,location) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,location=excluded.location',(updated['device_id'],name,updated['device_location']))
            elif action == 'demo':
                if db.execute('SELECT COUNT(*) FROM products').fetchone()[0] or db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]:
                    raise ValueError('Sample data is only available in an empty shop database.')
                self.demo(db)
            else:
                raise ValueError('Unknown action.')
            self.audit(db,action,{k:v for k,v in data.items() if k not in ('items','token')})
            event_id = self.record_event(db,before)
            self.queue_updates(db,action,data,result,event_id)
            return result

    def notification(self, db, ident, kind, phone, template, parameters, party_id=None, internal_id=None):
        if not template:
            return
        from notifications import whatsapp_number
        try:
            phone = whatsapp_number(phone)
        except ValueError:
            return
        db.execute('INSERT OR IGNORE INTO notifications(id,created,kind,party_id,phone,template,parameters,next_attempt,internal_id) VALUES(?,?,?,?,?,?,?,?,?)',
                   (ident,now(),kind,party_id,phone,template,json.dumps(parameters),now(),internal_id))

    def queue_updates(self, db, action, data, result, event_id):
        settings = self.settings(db)
        if not settings['whatsapp_enabled']:
            return
        summary = ''
        if action == 'sale' and result.get('id'):
            doc = db.execute('SELECT * FROM documents WHERE id=?',(result['id'],)).fetchone()
            customer = db.execute('SELECT * FROM parties WHERE id=?',(doc['party_id'],)).fetchone() if doc['party_id'] else None
            if customer and customer['whatsapp_opt_in']:
                self.notification(db,'invoice:'+doc['id'],'invoice',customer['phone'],settings['whatsapp_invoice_template'],
                                  [customer['name'],doc['id'],f"INR {doc['total']/100:.2f}"],party_id=customer['id'])
        if action == 'payment':
            customer = db.execute('SELECT * FROM parties WHERE id=?',(data.get('party_id'),)).fetchone()
            if customer and customer['kind']=='customer' and customer['whatsapp_opt_in']:
                self.notification(db,'payment:'+event_id,'payment',customer['phone'],settings['whatsapp_payment_template'],
                                  [customer['name'],f"INR {money(data['amount'])/100:.2f}",str(data.get('note') or 'Payment received')],party_id=customer['id'])
        from activity_alerts import summary as activity_summary,chunks
        summary=activity_summary(self,db,action,{**data,'_local':not data.get('_synced')},result,event_id)
        if summary:
            pages=chunks(summary)
            for recipient in db.execute('SELECT * FROM internal_contacts WHERE opt_in=1'):
                for i,part in enumerate(pages):
                    page_label=f" (part {i+1}/{len(pages)})" if len(pages)>1 else ''
                    self.notification(db,'internal:'+event_id+':'+str(recipient['id'])+':'+str(i),'internal',recipient['phone'],settings['whatsapp_internal_template'],
                                      [settings['name'],action.title()+page_label,part],internal_id=recipient['id'])
        if action in ('sale','purchase','product','adjust','transfer','sync','inventory_plan','purchase_order_status','reverse'):
            __import__('stock_alerts').queue(self,db)

    def queue_synced_updates(self, db, event):
        """A configured hub sender also handles business actions arriving from offline PCs."""
        payload=event['payload'];eid=event['id']
        from whatsapp_orders import notify
        for row in payload['masters'].get('trade_orders',[]):notify(db,self,row)
        for row in payload['masters'].get('purchase_orders',[]):self.queue_updates(db,'purchase_order_status',{'_synced':True},{'id':row['id']},eid+':po:'+row['id'])
        for row in payload['masters'].get('parties',[]):self.queue_updates(db,'party',{**row,'_synced':True},{'id':row['id']},eid+':profile:'+str(row['id']))
        if payload['masters'].get('products'):self.queue_updates(db,'import_products',{'_synced':True},{},eid+':catalogue')
        for recipe in payload.get('recipes',[]):self.queue_updates(db,'recipe',{'product_id':recipe['product_id'],'_synced':True},{},eid+':recipe:'+str(recipe['product_id']))
        for move in payload['append'].get('movements',[]):
            if move['reference']=='ADJUST':self.queue_updates(db,'adjust',{'location':move['location'],'note':move['note'],'_synced':True},{},eid+':adjust')
        for row in payload['masters'].get('documents',[]):
            if row.get('reversed'):
                self.queue_updates(db,'reverse',{'id':row['id']},{},eid+':'+row['id'])
            else:
                self.queue_updates(db,row['kind'],{}, {'id':row['id']},eid+':'+row['id'])
        for i,row in enumerate(payload['append'].get('payments',[])):
            self.queue_updates(db,'payment',{'party_id':row['party_id'],'amount':row['amount']/100,'note':row['note'],'method':row['method']},{},eid+':payment:'+str(i))
        for i,row in enumerate(payload['append'].get('expenses',[])):
            self.queue_updates(db,'expense',{'amount':row['amount']/100,'name':row['name'],'method':row['method']},{},eid+':expense:'+str(i))
        moves=payload['append'].get('movements',[])
        for row in moves:
            if row['reference'].startswith('TR-') and row['quantity']<0:
                target=next((r for r in moves if r['reference']==row['reference'] and r['product_id']==row['product_id'] and r['quantity']>0),None)
                if target:self.queue_updates(db,'transfer',{'product_id':row['product_id'],'quantity':-row['quantity'],'source':row['location'],'target':target['location']},{'id':row['reference']},eid+':'+row['reference'])
        self.queue_updates(db,'sync',{}, {},eid)

    def daily_update(self):
        with self.lock,self.connect() as db:
            settings=self.settings(db)
            __import__('stock_alerts').queue(self,db)
            if not settings['whatsapp_enabled'] or not settings['whatsapp_daily_time']:
                return
            from outreach import business_now
            local_now=business_now(settings)
            if local_now.time().replace(tzinfo=None) < dt.time.fromisoformat(settings['whatsapp_daily_time']):
                return
            day=local_now.date().isoformat()
            from activity_alerts import daily,chunks
            __import__('stock_alerts').queue(self,db)
            pages=chunks(daily(self,db,local_now))
            for recipient in db.execute('SELECT * FROM internal_contacts WHERE opt_in=1'):
                for i,part in enumerate(pages):
                    self.notification(db,f"daily:{day}:{recipient['id']}:{i}",'daily_summary',recipient['phone'],settings['whatsapp_internal_template'],
                                      [settings['name'],f'Daily summary {day} ({i+1}/{len(pages)})',part],internal_id=recipient['id'])

    def load_catalog(self, db):
        rows = json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
        count = 0
        for row in rows:
            if not db.execute('SELECT 1 FROM products WHERE sku=?',(row['sku'],)).fetchone():
                self.save_product(db,row)
                count += 1
        return {'count':count}

    def save_product(self, db, data):
        kind = data.get('kind','stock')
        if kind not in ('stock','ingredient','recipe'):
            raise ValueError('Invalid product type.')
        gst, cess = number(data.get('gst',0)), number(data.get('cess',0))
        if gst > 100 or cess > 100:
            raise ValueError('Tax rates must be between 0 and 100.')
        expiry = data.get('expiry','')
        if expiry:
            dt.date.fromisoformat(expiry)
        values = (required(data.get('name')),required(data.get('sku'),'SKU'),required(data.get('category'),'Category'),
                  required(data.get('unit'),'Unit'),money(data.get('price',0)),money(data.get('cost',0)),gst,cess,
                  str(data.get('hsn','')),number(data.get('minimum',5)),number(data.get('pack',1),True),expiry,kind)
        pid = data.get('id')
        if pid:
            old = db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
            if not old:
                raise ValueError('Product not found.')
            if old['kind'] != kind:
                raise ValueError('Product type cannot be changed. Create a new product.')
            db.execute('UPDATE products SET name=?,sku=?,category=?,unit=?,price=?,cost=?,gst=?,cess=?,hsn=?,minimum=?,pack=?,expiry=?,kind=? WHERE id=?',values+(pid,))
        else:
            pid = secrets.randbelow(2**50)+1
            db.execute('INSERT INTO products(id,name,sku,category,unit,price,cost,gst,cess,hsn,minimum,pack,expiry,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,)+values)
            opening = number(data.get('stock',0))
            if opening and kind != 'recipe':
                self.movement(db,pid,opening,'OPENING','Opening stock',data.get('location','Warehouse'))
        barcode = str(data.get('barcode','')).strip()
        if len(barcode) > 64:
            raise ValueError('Barcode is too long.')
        db.execute('UPDATE products SET barcode=? WHERE id=?',(barcode,pid))
        db.execute('UPDATE products SET tax_verified=? WHERE id=?',(int(data.get('tax_verified') in (True,'true','1','on',1)),pid))
        db.execute('UPDATE products SET brand=?,size=?,packaging=?,mrp=?,wholesale_price=? WHERE id=?',
                   (str(data.get('brand','')),str(data.get('size','')),str(data.get('packaging','')),money(data.get('mrp',0)),money(data.get('wholesale_price',0)),pid))
        return {'id':pid}

    def capture(self, db):
        return {t:[dict(r) for r in db.execute('SELECT * FROM '+t)] for t in
                ('products','parties','recipes','stocks','documents','lines','movements','payments','expenses','settings','devices','allocations','commerce_products','trade_orders','inventory_plans','purchase_orders')}

    def record_event(self, db, before):
        after = self.capture(db)
        payload = {'masters':{},'append':{},'deltas':{'stocks':[],'parties':[],'allocations':[]},'settings':[],'recipes':[]}
        for table in ('products','parties','documents','devices','commerce_products','trade_orders','inventory_plans','purchase_orders'):
            old = {r['id']:r for r in before[table]}
            changed = []
            for r in after[table]:
                row = dict(r)
                excluded = 'stock' if table == 'products' else 'balance' if table == 'parties' else None
                if excluded:
                    row.pop(excluded)
                prev = dict(old.get(r['id'],{}))
                if excluded:
                    prev.pop(excluded,None)
                if prev != row:
                    changed.append(row)
                if table == 'parties':
                    delta = r['balance']-old.get(r['id'],{}).get('balance',0)
                    if delta:
                        payload['deltas']['parties'].append({'id':r['id'],'delta':delta})
            payload['masters'][table] = changed
        oldstock = {(r['product_id'],r['location']):r['quantity'] for r in before['stocks']}
        for r in after['stocks']:
            delta = r['quantity']-oldstock.get((r['product_id'],r['location']),0)
            if delta:
                payload['deltas']['stocks'].append({'product_id':r['product_id'],'location':r['location'],'delta':delta})
        oldallocations = {(r['device_id'],r['product_id'],r['location']):r['quantity'] for r in before['allocations']}
        for r in after['allocations']:
            delta = r['quantity']-oldallocations.get((r['device_id'],r['product_id'],r['location']),0)
            if delta:
                payload['deltas']['allocations'].append({'device_id':r['device_id'],'product_id':r['product_id'],'location':r['location'],'delta':delta})
        for table in ('lines','movements','payments','expenses'):
            oldids = {r['id'] for r in before[table]}
            payload['append'][table] = [{k:v for k,v in r.items() if k != 'id'} for r in after[table] if r['id'] not in oldids]
        for pid in {r['product_id'] for r in before['recipes']+after['recipes']}:
            previous = [r for r in before['recipes'] if r['product_id'] == pid]
            current = [r for r in after['recipes'] if r['product_id'] == pid]
            if previous != current:
                payload['recipes'].append({'product_id':pid,'items':current})
        allowed = ('name','address','phone','gstin','state','gst_enabled','invoice_prefix','demo','admin_device_id','node_mode')
        prevsettings = {r['key']:r['value'] for r in before['settings']}
        payload['settings'] = [r for r in after['settings'] if r['key'] in allowed and r['value'] != prevsettings.get(r['key'])]
        eid = f'{time.time_ns():020d}-'+self.settings(db)['device_id']+'-'+secrets.token_hex(4)
        db.execute('INSERT INTO sync_events VALUES(?,?,?,?)',(eid,now(),self.settings(db)['device_id'],json.dumps(payload)))
        db.execute('INSERT INTO sync_seen VALUES(?)',(eid,))
        for table,rows in payload['masters'].items():
            for row in rows:
                db.execute('INSERT OR REPLACE INTO sync_versions VALUES(?,?)',(table+':'+str(row['id']),eid))
        for row in payload['recipes']:
            db.execute('INSERT OR REPLACE INTO sync_versions VALUES(?,?)',('recipe:'+str(row['product_id']),eid))
        for row in payload['settings']:
                db.execute('INSERT OR REPLACE INTO sync_versions VALUES(?,?)',('setting:'+row['key'],eid))
        return eid

    def apply_event(self, db, event):
        eid, payload = event['id'], event['payload']
        if db.execute('SELECT 1 FROM sync_seen WHERE id=?',(eid,)).fetchone():
            return False
        def newer(key):
            version = db.execute('SELECT version FROM sync_versions WHERE entity=?',(key,)).fetchone()
            if version and version[0] >= eid:
                return False
            db.execute('INSERT OR REPLACE INTO sync_versions VALUES(?,?)',(key,eid))
            return True
        admin = self.settings(db)['admin_device_id']
        incoming_admin = next((json.loads(r['value']) for r in payload['settings'] if r['key']=='admin_device_id'),None)
        unified=self.settings(db).get('node_mode')=='unified'
        if not unified and admin and incoming_admin and incoming_admin != admin:
            raise ValueError('Two main PCs were configured. Pair joining PCs with the existing business instead of creating another shop.')
        if not unified and admin and event['device'] != admin and (payload['masters'].get('products') or payload['recipes'] or payload['settings']):
            raise ValueError('Only the main PC may change catalogue, recipes or business settings.')
        __import__('procurement').validate_receipts(payload)
        for row in payload['masters'].get('purchase_orders',[]):__import__('procurement').validate_change(db,row,payload)
        for row in payload['masters'].get('inventory_plans',[]):__import__('procurement').validate_plan(row)
        for table in ('products','parties','documents','devices','commerce_products','trade_orders','inventory_plans','purchase_orders'):
            for row in payload['masters'].get(table,[]):
                if table=='trade_orders':
                    old=db.execute('SELECT invoice_id FROM trade_orders WHERE id=?',(row['id'],)).fetchone()
                    if old and old['invoice_id'] and old['invoice_id']!=row['invoice_id']:
                        raise ValueError('Order already invoiced on another node. Review this sync conflict before retrying.')
                if table=='documents':
                    old=db.execute('SELECT * FROM documents WHERE id=?',(row['id'],)).fetchone()
                    if old:
                        same={k:v for k,v in dict(old).items() if k!='reversed'}=={k:v for k,v in row.items() if k!='reversed'}
                        if not same or old['reversed'] or not row['reversed']:
                            raise ValueError('Invoice already changed or reversed on another node. Review this transaction.')
                if not newer(table+':'+str(row['id'])):
                    continue
                permitted = {r[1] for r in db.execute('PRAGMA table_info('+table+')')}-({'stock'} if table == 'products' else {'balance'} if table == 'parties' else set())
                if not set(row) <= permitted:
                    raise ValueError('Invalid synced fields.')
                cols = list(row)
                db.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+') ON CONFLICT(id) DO UPDATE SET '+','.join(k+'=excluded.'+k for k in cols if k != 'id'),tuple(row.values()))
        for row in ([] if unified else payload['deltas'].get('allocations',[])):
            actor,pid,loc,delta = row['device_id'],row['product_id'],self.location(row['location']),float(row['delta'])
            if not __import__('math').isfinite(delta):
                raise ValueError('Invalid stock allocation.')
            if admin and event['device'] not in (admin,actor):
                raise ValueError('A PC cannot change another till’s stock allowance.')
            db.execute('INSERT OR IGNORE INTO allocations VALUES(?,?,?,0)',(actor,pid,loc))
            previous = db.execute('SELECT quantity FROM allocations WHERE device_id=? AND product_id=? AND location=?',(actor,pid,loc)).fetchone()[0]
            if previous+delta < -0.000001:
                raise ValueError('Missing earlier stock allocation or conflicting PC allowance. Sync again after the main PC uploads.')
            db.execute('UPDATE allocations SET quantity=ROUND(quantity+?,6) WHERE device_id=? AND product_id=? AND location=?',(delta,actor,pid,loc))
        for row in payload['deltas']['stocks']:
            pid,loc,delta = row['product_id'],self.location(row['location']),float(row['delta'])
            if not __import__('math').isfinite(delta):
                raise ValueError('Invalid synced stock quantity.')
            db.execute('INSERT OR IGNORE INTO stocks VALUES(?,?,0)',(pid,loc))
            stock = db.execute('SELECT quantity FROM stocks WHERE product_id=? AND location=?',(pid,loc)).fetchone()[0]
            if stock+delta < -0.000001:
                raise ValueError('Stock conflict or missing earlier transaction. Keep both PCs synced; do not edit sync files.')
            db.execute('UPDATE stocks SET quantity=ROUND(quantity+?,6) WHERE product_id=? AND location=?',(delta,pid,loc))
            db.execute('UPDATE products SET stock=ROUND(stock+?,6) WHERE id=?',(delta,pid))
        for row in payload['deltas']['parties']:
            p = db.execute('SELECT balance,kind,credit_limit FROM parties WHERE id=?',(row['id'],)).fetchone()
            if not p or p[0]+row['delta'] < 0:
                raise ValueError('Ledger conflict or missing earlier transaction. Review payments on both PCs.')
            if p['kind']=='customer' and p['credit_limit']>0 and p['balance']+row['delta']>p['credit_limit']:
                raise ValueError('Concurrent credit exceeds the customer limit. Reconcile this transaction before retrying.')
            db.execute('UPDATE parties SET balance=balance+? WHERE id=?',(row['delta'],row['id']))
        for table in ('lines','movements','payments','expenses'):
            for row in payload['append'].get(table,[]):
                permitted = {r[1] for r in db.execute('PRAGMA table_info('+table+')')}-{'id'}
                if set(row) != permitted:
                    raise ValueError('Invalid synced transaction.')
                cols = list(row)
                db.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',tuple(row.values()))
        for recipe in payload['recipes']:
            if newer('recipe:'+str(recipe['product_id'])):
                db.execute('DELETE FROM recipes WHERE product_id=?',(recipe['product_id'],))
                for item in recipe['items']:
                    db.execute('INSERT INTO recipes VALUES(?,?,?)',(item['product_id'],item['ingredient_id'],item['quantity']))
        for row in payload['settings']:
            if row['key'] not in ('name','address','phone','gstin','state','gst_enabled','invoice_prefix','demo','admin_device_id','node_mode'):
                raise ValueError('Invalid synced setting.')
            if newer('setting:'+row['key']):
                db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(row['key'],row['value']))
        db.execute('INSERT INTO sync_seen VALUES(?)',(eid,))
        db.execute('DELETE FROM sync_errors WHERE id=?',(eid,))
        self.audit(db,'sync imported',{'event':eid,'device':event['device']})
        for doc in payload['masters'].get('documents',[]):
            if doc['kind']=='sale' and not doc.get('reversed'):
                self.queue_updates(db,'sale',{}, {'id':doc['id']},eid)
            elif doc['kind']=='purchase' and not doc.get('reversed'):
                self.queue_updates(db,'purchase',{}, {'id':doc['id']},eid+':'+doc['id'])
        transfers={}
        for movement in payload['append'].get('movements',[]):
            if movement['reference'].startswith('TR'):
                key=(movement['reference'],movement['product_id'])
                transfers.setdefault(key,[]).append(movement)
        for (reference,pid),rows in transfers.items():
            source=next((r for r in rows if r['quantity']<0),None)
            target=next((r for r in rows if r['quantity']>0),None)
            if source and target:
                self.queue_updates(db,'transfer',{'product_id':pid,'quantity':target['quantity'],'source':source['location'],'target':target['location']},{'id':reference},eid+':'+reference)
        for payment in payload['append'].get('payments',[]):
            self.queue_updates(db,'payment',{'party_id':payment['party_id'],'amount':payment['amount']/100,'note':payment['note']},{},eid)
        self.queue_updates(db,'sync',{}, {},eid)
        return True

    def sync(self):
        with self.connect() as db:
            cloud = self.settings(db).get('cloud_url')
        if cloud:
            from cloud_sync import sync_desktop
            return sync_desktop(self)
        with self.lock:
            with self.connect() as db:
                settings = self.settings(db)
                if not settings['sync_folder'] or not settings['device_location']:
                    raise ValueError('Set this PC’s location and a shared sync folder in Settings first.')
                folder = Path(settings['sync_folder']).expanduser()/'AlHidayaSync-v1'
                folder.mkdir(parents=True,exist_ok=True)
                events = list(db.execute('SELECT * FROM sync_events'))
            for event in events:
                target = folder/(event['id']+'.json')
                if not target.exists():
                    temp = folder/(event['id']+'.tmp')
                    temp.write_text(json.dumps({'version':3,'id':event['id'],'date':event['date'],'device':event['device'],'payload':json.loads(event['payload'])}),encoding='utf-8')
                    temp.replace(target)
            imported = 0
            pending = sorted(folder.glob('*.json'))
            for attempt in range(3):
                retry, progress = [], 0
                for path in pending:
                    try:
                        if path.stat().st_size > 10000000:
                            raise ValueError('Sync file exceeds size limit.')
                        event = json.loads(path.read_text(encoding='utf-8'))
                        if event.get('version') not in (1,2,3) or event.get('id')+'.json' != path.name:
                            raise ValueError('Unsupported sync file.')
                        with self.connect() as db:
                            if self.apply_event(db,event):
                                imported += 1
                                progress += 1
                    except Exception as e:
                        with self.connect() as db:
                            db.execute('INSERT OR REPLACE INTO sync_errors VALUES(?,?)',(path.stem,str(e)[:300]))
                        retry.append(path)
                pending = retry
                if not pending or not progress:
                    break
            with self.connect() as db:
                db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(now()),'last_sync'))
            return {'imported':imported,'pending':len(pending),'message':f'{imported} transactions imported; {len(pending)} need attention. Cloud upload is handled by your folder provider.'}

    def method(self, value):
        if value not in ('Cash','UPI','Card','Bank'):
            raise ValueError('Select a valid payment method.')
        return value

    def document(self, db, kind, data):
        order_id=str(data.get('trade_order_id','')) if kind=='sale' else ''
        trade_order=None
        if order_id:
            trade_order=db.execute('SELECT * FROM trade_orders WHERE id=?',(order_id,)).fetchone()
            if not trade_order or trade_order['invoice_id'] or trade_order['status'] not in ('confirmed','packing','ready') or json.loads(trade_order['issues']):
                raise ValueError('Confirm and resolve this unbilled WhatsApp order before invoicing.')
            expected={}
            for l in json.loads(trade_order['items']):expected[l['product_id']]=expected.get(l['product_id'],0)+l['quantity']
            supplied={}
            for l in data.get('items',[]):supplied[int(l['product_id'])]=supplied.get(int(l['product_id']),0)+number(l['quantity'],True)
            if supplied!=expected or data.get('location')!=trade_order['location']:
                raise ValueError('Order items or location differ from the confirmed WhatsApp order.')
        purchase_order=__import__('procurement').check_receipt(db,data) if kind=='purchase' else None
        items = data.get('items',[])
        if not items:
            raise ValueError('Add at least one item.')
        settings = self.settings(db)
        location = self.location(data.get('location','Outlet' if kind == 'sale' else 'Warehouse'))
        pid = data.get('party_id') or None
        party = dict(db.execute('SELECT * FROM parties WHERE id=?',(pid,)).fetchone() or {}) if pid else {}
        if pid and party.get('kind') != ('customer' if kind == 'sale' else 'supplier'):
            raise ValueError('Select the correct customer or supplier.')
        if kind == 'purchase' and not party:
            raise ValueError('Select a supplier.')
        supply_state = str(data.get('supply_state') or (party.get('gstin','')[:2] if party.get('gstin') else settings['state']))
        if settings['gst_enabled']:
            import re
            if not re.fullmatch(r'[0-9]{2}',supply_state):
                raise ValueError('Enter a two-digit place-of-supply state code.')
        interstate = bool(settings['gst_enabled'] and supply_state != settings['state'])
        prepared, gross = [], 0
        for item in items:
            p = db.execute('SELECT * FROM products WHERE id=?',(int(item['product_id']),)).fetchone()
            if not p:
                raise ValueError('Product not found.')
            if kind == 'sale' and p['kind'] == 'ingredient':
                raise ValueError('Ingredients cannot be billed directly.')
            if kind == 'sale' and p['price'] <= 0:
                raise ValueError('Set a selling price before billing: '+p['name'])
            if settings['gst_enabled'] and not p['tax_verified']:
                raise ValueError('Confirm HSN/SAC and tax rate before GST billing: '+p['name'])
            if settings['gst_enabled'] and not p['hsn'].isdigit():
                raise ValueError('Enter HSN/SAC before GST billing: '+p['name'])
            if kind == 'sale' and p['expiry'] and p['expiry'] < dt.date.today().isoformat():
                raise ValueError('Expired stock cannot be sold: '+p['name'])
            if kind == 'purchase' and p['kind'] == 'recipe':
                raise ValueError('Receive ingredients, not prepared café products.')
            qty = number(item['quantity'],True)
            price = money(item['price']) if kind == 'purchase' else p['wholesale_price'] if data.get('price_tier') == 'wholesale' and p['wholesale_price'] > 0 else p['price']
            if kind == 'sale' and p['mrp'] > 0 and price > p['mrp']:
                raise ValueError('Selling price exceeds MRP: '+p['name'])
            linegross = int((Decimal(price)*Decimal(str(qty))).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            gross += linegross
            prepared.append({'p':dict(p),'quantity':qty,'price':price,'gross':linegross})
        discount = money(data.get('discount',0)) if kind == 'sale' else 0
        if discount > gross:
            raise ValueError('Discount cannot exceed the bill total.')
        total = gross-discount
        allocated, taxsum = 0, 0
        ident = ('S' if kind == 'sale' else 'P')
        year = dt.date.today().year if dt.date.today().month >= 4 else dt.date.today().year-1
        prefix = f"{settings['invoice_prefix']}{settings['device_id'][:6].upper()}{ident}{str(year)[-2:]}"
        count = db.execute('SELECT COUNT(*) FROM documents WHERE id LIKE ?',(prefix+'%',)).fetchone()[0]+1
        if count > 99999:
            raise ValueError('Invoice sequence is full. Start a new invoice prefix.')
        docid = prefix+str(count).zfill(5)
        snapshot = {'shop':{k:settings[k] for k in ('name','address','phone','gstin','state','gst_enabled')},'party':party,'items':[],
                    'location':location,'supply_state':supply_state,'tax_type':'IGST' if interstate else 'CGST + SGST','device_id':settings['device_id']}
        if order_id:snapshot['trade_order_id']=order_id
        for i,line in enumerate(prepared):
            p,qty = line['p'],line['quantity']
            share = discount-allocated if i == len(prepared)-1 else int(Decimal(discount)*Decimal(line['gross'])/Decimal(gross)) if gross else 0
            allocated += share
            amount = line['gross']-share
            rate = Decimal(str(p['gst']))+Decimal(str(p['cess'])) if settings['gst_enabled'] else Decimal(0)
            taxable = int((Decimal(amount)*100/(100+rate)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            tax = amount-taxable
            cessamount = int((Decimal(tax)*Decimal(str(p['cess']))/rate).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if rate else 0
            gstamount = tax-cessamount
            taxsum += tax
            cost = int(Decimal(p['cost'])*Decimal(str(qty)))
            if p['kind'] == 'recipe':
                recipe = list(db.execute('SELECT r.*,p.cost FROM recipes r JOIN products p ON p.id=r.ingredient_id WHERE product_id=?',(p['id'],)))
                if not recipe:
                    raise ValueError('Set up the recipe for '+p['name']+' before billing.')
                cost = 0
                for r in recipe:
                    used = qty*r['quantity']
                    self.movement(db,r['ingredient_id'],-used,docid,'Café recipe: '+p['name'],location)
                    cost += int(Decimal(r['cost'])*Decimal(str(used)))
            else:
                self.movement(db,p['id'],qty if kind == 'purchase' else -qty,docid,kind.title(),location)
                if kind == 'purchase':
                    oldvalue = Decimal(str(p['stock']))*p['cost']
                    newcost = int(((oldvalue+Decimal(str(qty))*line['price'])/Decimal(str(p['stock']+qty))).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                    db.execute('UPDATE products SET cost=? WHERE id=?',(newcost,p['id']))
            snapshot['items'].append({'product_id':p['id'],'name':p['name'],'sku':p['sku'],'unit':p['unit'],'hsn':p['hsn'],
                'quantity':qty,'price':line['price'],'total':amount,'tax':tax,'cost':cost,'gst':p['gst'] if settings['gst_enabled'] else 0,
                'cess':p['cess'] if settings['gst_enabled'] else 0,'taxable':taxable,'gst_amount':gstamount,'cess_amount':cessamount,
                'cgst_amount':0 if interstate else gstamount//2,'sgst_amount':0 if interstate else gstamount-gstamount//2,
                'igst_amount':gstamount if interstate else 0})
        if purchase_order:snapshot['purchase_order_id']=purchase_order['id']
        paid = money(data.get('paid',total/100))
        if paid > total:
            raise ValueError('Amount received cannot exceed the total. Record change separately.')
        if paid < total and not party:
            raise ValueError('Select a customer before creating a credit bill.')
        if kind == 'sale' and party and party.get('credit_limit',0)>0 and party['balance']+total-paid > party['credit_limit']:
            raise ValueError('This sale would exceed the customer’s credit limit. Collect more payment or review the customer’s credit limit.')
        if settings.get('node_mode')!='unified' and kind == 'sale' and settings['device_location'] and settings['admin_device_id'] and settings['device_id'] != settings['admin_device_id'] and paid < total:
            raise ValueError('In serverless mode, credit bills are issued at the main trading counter. Additional tills require full payment to avoid conflicting offline customer credit.')
        payment = self.method(data.get('payment','Cash'))
        db.execute('INSERT INTO documents(id,kind,date,party_id,total,tax,paid,payment,discount,reference,snapshot,location) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                   (docid,kind,now(),pid,total,taxsum,paid,payment,discount,str(data.get('reference','')),json.dumps(snapshot),location))
        for item in snapshot['items']:
            db.execute('INSERT INTO lines(document_id,product_id,name,quantity,price,total,tax,cost,gst,cess,hsn) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (docid,)+tuple(item[k] for k in ('product_id','name','quantity','price','total','tax','cost','gst','cess','hsn')))
        if party:
            db.execute('UPDATE parties SET balance=balance+? WHERE id=?',(total-paid,pid))
        if purchase_order:__import__('procurement').receive(db,purchase_order,snapshot['items'])
        if trade_order:
            if total!=trade_order['total']:raise ValueError('The order price changed. Review and confirm it again before billing.')
            db.execute('UPDATE trade_orders SET invoice_id=?,updated=? WHERE id=?',(docid,now(),order_id))
            from whatsapp_orders import notify
            notify(db,self,db.execute('SELECT * FROM trade_orders WHERE id=?',(order_id,)).fetchone())
        return {'id':docid}

    def reverse(self, db, data):
        doc = db.execute('SELECT * FROM documents WHERE id=?',(data['id'],)).fetchone()
        if not doc or doc['reversed']:
            raise ValueError('Document is missing or already reversed.')
        location = self.settings(db)['device_location']
        if self.settings(db).get('node_mode')!='unified' and location and doc['location'] != location:
            raise ValueError('Reverse this document on the PC that issued it.')
        snapshot = json.loads(doc['snapshot'])
        if self.settings(db).get('node_mode')!='unified' and snapshot.get('device_id') and snapshot['device_id'] != self.settings(db)['device_id']:
            raise ValueError('Reverse this document on its issuing PC, then sync.')
        reason = required(data.get('reason'),'Reason')
        outstanding = doc['total']-doc['paid']
        if doc['party_id'] and outstanding:
            party = db.execute('SELECT * FROM parties WHERE id=?',(doc['party_id'],)).fetchone()
            if party['balance'] < outstanding or db.execute('SELECT 1 FROM payments WHERE party_id=? AND date>=?',(doc['party_id'],doc['date'])).fetchone():
                raise ValueError('Payments have been recorded after this bill. An accountant must reconcile them before reversal.')
            db.execute('UPDATE parties SET balance=balance-? WHERE id=?',(outstanding,doc['party_id']))
        for m in list(db.execute('SELECT * FROM movements WHERE reference=?',(doc['id'],))):
            self.movement(db,m['product_id'],-m['quantity'],'REV-'+doc['id'],reason,m['location'])
        if doc['kind']=='purchase':__import__('procurement').reverse(db,doc)
        db.execute('UPDATE documents SET reversed=1 WHERE id=?',(doc['id'],))
        return {'refund':doc['paid'],'method':doc['payment']}

    def backup(self, local_only=False):
        with self.lock, self.connect() as source:
            settings = self.settings(source)
            folders = [self.folder/'backups']
            if settings['backup_folder'] and not local_only:
                folders.append(Path(settings['backup_folder']).expanduser())
            name = 'AlHidaya-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3'
            paths = []
            for folder in folders:
                folder.mkdir(parents=True,exist_ok=True)
                target = folder/name
                with sqlite3.connect(target, factory=ClosingConnection) as destination:
                    source.backup(destination)
                    if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('Backup integrity check failed.')
                if (self.folder/'media').exists():
                    import shutil
                    shutil.copytree(self.folder/'media',target.with_suffix('.media'),dirs_exist_ok=True)
                paths.append(str(target))
            source.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(now()),'last_backup'))
            return {'paths':paths,'message':'Verified database backup saved. Your cloud-folder app handles upload when online.'}

    def demo(self, db):
        products = [
            ('Coca-Cola 250 ml','890176401','Cold drinks','bottle',20,15,40,0,'220210',144,24,24,'stock'),
            ('Sprite 750 ml','890176402','Cold drinks','bottle',45,34,40,0,'220210',72,12,24,'stock'),
            ('Thums Up 250 ml','890176403','Cold drinks','bottle',20,15,40,0,'220210',18,24,24,'stock'),
            ('Bisleri 1 L','890176404','Water','bottle',20,13,5,0,'220110',120,24,12,'stock'),
            ('Paper Boat Mango','890176405','Juices','pack',30,22,5,0,'220299',48,12,12,'stock'),
            ('Soda','ING-SODA','Ingredients','ml',0,.025,0,0,'',12000,2000,1,'ingredient'),
            ('Mint syrup','ING-MINT','Ingredients','ml',0,.3,0,0,'',1500,500,1,'ingredient'),
            ('Milk','ING-MILK','Ingredients','ml',0,.06,0,0,'',5000,1000,1,'ingredient'),
            ('Coffee powder','ING-COFFEE','Ingredients','g',0,1.2,0,0,'',500,100,1,'ingredient'),
            ('Classic mint mojito','CAFE-001','Mojitos','cup',80,0,5,0,'996331',0,0,1,'recipe'),
            ('Hot coffee','CAFE-002','Coffee','cup',40,0,5,0,'996331',0,0,1,'recipe')]
        ids = []
        for name,sku,category,unit,price,cost,gst,cess,hsn,stock,minimum,pack,kind in products:
            pid = secrets.randbelow(2**50)+1
            ids.append(pid)
            db.execute('INSERT INTO products(id,name,sku,category,unit,price,cost,gst,cess,hsn,minimum,pack,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (pid,name,sku,category,unit,money(price),money(cost),gst,cess,hsn,minimum,pack,kind))
            if stock:
                self.movement(db,pid,stock,'DEMO','Sample opening stock')
        db.executemany('INSERT INTO recipes VALUES(?,?,?)',[(ids[9],ids[5],200),(ids[9],ids[6],30),(ids[10],ids[7],150),(ids[10],ids[8],8)])
        db.executemany('INSERT INTO parties(id,name,phone,kind) VALUES(?,?,?,?)',[(secrets.randbelow(2**50)+1,'Neighbourhood Store','','customer'),(secrets.randbelow(2**50)+1,'Local Beverage Distributor','','supplier')])
        db.execute('UPDATE settings SET value=? WHERE key=?',('true','demo'))

class Handler(BaseHTTPRequestHandler):
    shop = None
    def log_message(self, *args):
        pass
    def send(self, status, body, mime='application/json'):
        raw = json.dumps(body).encode() if mime == 'application/json' else body
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(raw)
    def valid_host(self):
        return self.headers.get('Host','') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
    def do_GET(self):
        if not self.valid_host():
            return self.send(403,{'error':'Local access only.'})
        path = urlparse(self.path).path
        if path.startswith('/media/'):
            from media_catalogue import asset_path
            try:
                ident=path[7:]
                with self.shop.connect() as db:r=db.execute('SELECT mime FROM media_assets WHERE id=?',(ident,)).fetchone()
                return self.send(200,asset_path(self.shop,ident).read_bytes(),r['mime']) if r else self.send(404,{'error':'Image not found.'})
            except (ValueError,OSError):return self.send(404,{'error':'Image not found.'})
        if path == '/api/session':
            return self.send(200,{'token':TOKEN})
        if path == '/api/state':
            return self.send(200,self.shop.state())
        if path == '/api/backup-download':
            with self.shop.lock, self.shop.connect() as source:
                target = self.shop.folder/'download.sqlite3'
                with sqlite3.connect(target, factory=ClosingConnection) as destination:
                    source.backup(destination)
                return self.send(200,target.read_bytes(),'application/vnd.sqlite3')
        files = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
        if path not in files:
            return self.send(404,{'error':'Not found'})
        f = ROOT/'static'/files[path]
        content = f.read_bytes()
        return self.send(200,content,{'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[f.suffix[1:]])
    def do_POST(self):
        if not self.valid_host() or self.headers.get('X-Shop-Token') != TOKEN:
            return self.send(403,{'error':'Please reopen the app.'})
        if self.headers.get('Origin') and self.headers['Origin'] not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
            return self.send(403,{'error':'Local access only.'})
        try:
            size = int(self.headers.get('Content-Length',0))
            if size < 1 or size > 8000000:
                raise ValueError('Invalid request size.')
            data = json.loads(self.rfile.read(size))
            path = urlparse(self.path).path
            if not path.startswith('/api/'):
                raise ValueError('Unknown endpoint.')
            if path == '/api/shutdown':
                self.shop.backup(local_only=True)
                self.send(200,{'message':'Backup saved. App closed. You can close this browser tab.'})
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            result = self.shop.act(path[5:],data)
            self.send(200,result)
        except (ValueError,KeyError,TypeError,sqlite3.IntegrityError,DecimalException) as e:
            self.send(400,{'error':str(e)})
        except Exception:
            self.send(500,{'error':'Could not complete this operation. No partial transaction was saved. Check folder permissions or retry.'})

from decimal import DecimalException

def restore_backup(shop, source):
    source = Path(source).resolve()
    if source == shop.path.resolve():
        raise ValueError('Choose a backup file, not the live database.')
    with sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True,factory=ClosingConnection) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Invalid backup.')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'products','documents','settings','audit','movements','parties','recipes','payments','lines','expenses'} <= tables:
            raise ValueError('Not an Al Hadiya backup.')
        shop.backup()
        with shop.connect() as target:
            db.backup(target)
        if source.with_suffix('.media').is_dir():
            import shutil
            shutil.copytree(source.with_suffix('.media'),shop.folder/'media',dirs_exist_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--data-dir',type=Path,default=DATA)
    parser.add_argument('--restore',type=Path)
    parser.add_argument('--backup-only',action='store_true')
    args = parser.parse_args()
    shop = Shop(args.data_dir)
    if args.backup_only:
        shop.backup(local_only=True)
        return
    if args.restore:
        restore_backup(shop,args.restore)
        print('Backup restored. Start the app normally.')
        return
    Handler.shop = shop
    try:
        server = ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    except OSError:
        try:
            import urllib.request
            with urllib.request.urlopen(url if 'url' in locals() else f'http://127.0.0.1:{args.port}/api/state',timeout=2) as response:
                if not json.load(response).get('local'):
                    raise ValueError('Port in use')
            if not args.no_browser:
                webbrowser.open(f'http://127.0.0.1:{args.port}')
        except Exception:
            if os.name == 'nt':
                __import__('ctypes').windll.user32.MessageBoxW(0,'The app port is occupied. Close the other app and try again.','Al Hadiya Traders',0)
            else:
                print('App port is occupied. Close the other app or use --port.')
        return
    url = f'http://127.0.0.1:{args.port}'
    print('Al Hadiya Traders:',url,'\nData:',shop.path,'\nKeep this window open. Ctrl+C to close.')
    if not args.no_browser:
        webbrowser.open(url)
    def autobackup():
        ticks = 0
        while not stop.wait(30):
            ticks += 1
            try:
                if ticks % 30 == 0:
                    shop.backup()
                with shop.connect() as db:
                    if shop.settings(db)['sync_folder'] or shop.settings(db).get('cloud_url'):
                        shop.sync()
                shop.daily_update()
                from notifications import process_outbox
                process_outbox(shop)
            except Exception:
                pass  # UI exposes last successful backup; billing stays available.
    stop = threading.Event()
    threading.Thread(target=autobackup,daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        try:
            shop.backup()
        except Exception:
            print('Closing backup failed; the live database remains saved.')

if __name__ == '__main__':
    main()
