"""Shared offline/online staff authentication and permissions."""
import hashlib,hmac,secrets,threading,time,sqlite3,logging
from http.cookies import SimpleCookie

ROLES={'owner','manager','cashier','viewer'}
MANAGER={'product','party','recipe','purchase','payment','expense','transfer','adjust','reverse','import_products','sale','trade_order_status','trade_order_reprice','inventory_plan','purchase_order_create','purchase_order_status'}
CASHIER={'sale','party','expense'}
SETTINGS={'name','address','phone','gstin','state','gst_enabled','invoice_prefix','printer'}
def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt,hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()

class StaffAccess:
    def __init__(self,folder,origin,secure=True,local=False,shop=None):
        from app import Shop
        self.shop=shop or Shop(folder);self.origin=origin.rstrip('/');self.secure=secure;self.local=local
        if not local:
            from cloud_sync import Hub
            self.hub=Hub(self.shop)
        self.failed={};self.order_attempts={};self.lock=threading.RLock()
        with self.shop.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS web_users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,name TEXT,role TEXT,location TEXT,salt TEXT,password_hash TEXT,active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS web_sessions(digest TEXT PRIMARY KEY,user_id INTEGER REFERENCES web_users(id),csrf TEXT,expires REAL);
            CREATE TABLE IF NOT EXISTS web_audit(id INTEGER PRIMARY KEY,created REAL,user_id INTEGER,action TEXT);''')
    def user(self,data):
        name=str(data.get('username','')).strip().lower()
        if not name or len(name)>64 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_.-' for c in name):raise ValueError('Use a username of letters, numbers, dots, hyphens or underscores.')
        role=data.get('role','cashier');location=data.get('location','Warehouse')
        if role not in ROLES or location not in ('Warehouse','Outlet'):raise ValueError('Choose a valid role and location.')
        password=str(data.get('password',''))
        if not 12<=len(password)<=256:raise ValueError('Use a password of 12 to 256 characters.')
        salt,digest=password_hash(password)
        with self.shop.lock,self.shop.connect() as db:
            db.execute('INSERT INTO web_users(username,name,role,location,salt,password_hash) VALUES(?,?,?,?,?,?)',(name,str(data.get('name') or name),role,location,salt,digest))
            self.shop.audit(db,'staff_account_created',{'username':name,'role':role,'location':location})
    def login(self,username,password,ip):
        if not isinstance(username,str) or not isinstance(password,str) or len(username)>64 or len(password)>256:return None
        with self.lock:
            recent=[t for t in self.failed.get(ip,[]) if time.time()-t<60]
            self.failed[ip]=recent
            if len(recent)>=8:return None
            if len(self.failed)>10000:self.failed={ip:recent}
            with self.shop.connect() as db:
                user=db.execute('SELECT * FROM web_users WHERE username=? AND active=1',(username.strip().lower(),)).fetchone()
                salt=user['salt'] if user else '00'*16
                valid=user and hmac.compare_digest(password_hash(password,salt)[1],user['password_hash'])
                if not valid:
                    # Hash even unknown usernames to reduce timing differences.
                    if not user:password_hash(password,salt)
                    recent.append(time.time());return None
                token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
                db.execute('DELETE FROM web_sessions WHERE expires<?',(time.time(),))
                db.execute('INSERT INTO web_sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,time.time()+4*3600))
                db.execute('INSERT INTO web_audit(created,user_id,action) VALUES(?,?,?)',(time.time(),user['id'],'login'))
                return token
    def session(self,cookie):
        c=SimpleCookie()
        try:c.load(cookie or '')
        except Exception:return None
        token=c.get('ah_session')
        if not token:return None
        with self.shop.connect() as db:
            row=db.execute('SELECT u.id,u.username,u.name,u.role,u.location,s.csrf,s.digest FROM web_sessions s JOIN web_users u ON u.id=s.user_id WHERE s.digest=? AND s.expires>? AND u.active=1',(hashlib.sha256(token.value.encode()).hexdigest(),time.time())).fetchone()
            return dict(row) if row else None
    def state(self,user):
        result=self.shop.state();s=result['settings'];allocated=result['allocations']
        if not self.local:
            for key in ('sync_folder','backup_folder','last_backup','last_sync'):s[key]=''
        result['local']=self.local;result['online']=not self.local;result['web_user']={k:user[k] for k in ('id','username','name','role','location') if k in user}
        s['device_location']=user['location']
        result['release_version']=__import__('pathlib').Path(__file__).with_name('VERSION').read_text().strip()
        if user['role']!='owner':
            result['whatsapp_sessions']=[];result['commerce_products']=[];result['media_assets']=[];result['catalogue_products']=[];result['catalogue_orders']=[];result['internal_contacts']=[];result['notifications']=[];result['campaigns']=[];result['whatsapp_templates']=[];result['whatsapp_webhook_configured']=False;result['whatsapp_token_configured']=False
            for key in tuple(s):
                if key.startswith('whatsapp_'):s[key]=False if isinstance(s[key],bool) else ''
            result['devices']=[];result['allocations']=[];result['sync_errors']=[]
        if user['role'] in ('cashier','viewer'):
            result['trade_orders']=[];result['purchase_orders']=[];result['inventory_plans']=[];result['inventory_planning']=[];result['stock_alerts']=[]
            result['stocks']=[r for r in result['stocks'] if r['location']==user['location']]
            for p in result['products']:
                p['stock']=sum(r['quantity'] for r in result['stocks'] if r['product_id']==p['id'])
                p['cost']=0
            for d in result['documents']:
                if d['kind']=='sale':
                    for line in d['snapshot']['items']:line['cost']=0
            for line in result['lines']:line['cost']=0
            result['documents']=[d for d in result['documents'] if d['location']==user['location'] and d['kind']=='sale']
            ids={d['id'] for d in result['documents']}
            result['lines']=[r for r in result['lines'] if r['document_id'] in ids]
            result['movements']=[r for r in result['movements'] if r['location']==user['location']]
            result['payments']=[];result['expenses']=[]
            result['parties']=[p for p in result['parties'] if p['kind']=='customer']
        return result
    def act(self,user,action,data):
        role=user['role']
        if role=='viewer':raise PermissionError('This account is read-only.')
        if role=='cashier' and action not in CASHIER:raise PermissionError('Cashier permission does not allow this operation.')
        if role=='manager' and action not in MANAGER:raise PermissionError('Owner permission is required.')
        if not self.local and action in ('sync','shutdown','cloud_pair','cloud_address','cloud_disconnect','cloud_retire'):
            raise ValueError('This local-device operation is unavailable in the hosted review.')
        if not self.local and action=='settings':data={k:v for k,v in data.items() if k in SETTINGS}
        if role in ('manager','cashier'):
            if action in ('sale','purchase','expense','adjust','product','inventory_plan','purchase_order_create'):data['location']=user['location']
            if action=='purchase_order_status':
                with self.shop.connect() as db:
                    order=db.execute('SELECT location FROM purchase_orders WHERE id=?',(data.get('id'),)).fetchone()
                if not order or order['location']!=user['location']:raise PermissionError('This purchase order belongs to another location.')
            if action in ('trade_order_status','trade_order_reprice') and user['location']!='Warehouse':raise PermissionError('Trading orders require Warehouse permission.')
            if action=='import_products':
                data['rows']=[{**row,'location':user['location']} for row in data.get('rows',[])]
            if action=='transfer' and data.get('source')!=user['location']:raise PermissionError('Transfer stock from your assigned location.')
            if action=='reverse':
                with self.shop.connect() as db:
                    doc=db.execute('SELECT location FROM documents WHERE id=?',(data.get('id'),)).fetchone()
                    if not doc or doc['location']!=user['location']:raise PermissionError('This invoice belongs to another location.')
        if role=='cashier' and action=='party':
            if data.get('kind')!='customer':raise PermissionError('Cashiers can create customer profiles only.')
            with self.shop.connect() as db:
                old=db.execute('SELECT credit_limit FROM parties WHERE id=?',(data.get('id'),)).fetchone()
            data['credit_limit']=(old['credit_limit']/100) if old else 0
        result=self.shop.act(action,data)
        if self.local and action=='cloud_pair':
            with self.shop.connect() as db:db.execute('UPDATE web_users SET location=? WHERE id=?',(self.shop.settings(db)['device_location'],user['id']))
        try:
            with self.shop.connect() as db:db.execute('INSERT INTO web_audit(created,user_id,action) VALUES(?,?,?)',(time.time(),user['id'],action))
        except sqlite3.Error:
            logging.getLogger('alhadiya').warning('Business operation saved; staff audit write unavailable.')
            result={**result,'warning':'Saved successfully; staff audit write unavailable.'}
        return result

    def active(self,current,ident,enabled):
        ident=int(ident)
        if ident==current['id'] and not enabled:raise ValueError('You cannot disable your current account.')
        with self.shop.lock,self.shop.connect() as db:
            row=db.execute('SELECT role FROM web_users WHERE id=?',(ident,)).fetchone()
            if not row:raise ValueError('Account not found.')
            if row['role']=='owner' and not enabled and db.execute("SELECT COUNT(*) FROM web_users WHERE role='owner' AND active=1").fetchone()[0]<=1:raise ValueError('At least one owner must remain active.')
            db.execute('UPDATE web_users SET active=? WHERE id=?',(int(enabled),ident));db.execute('DELETE FROM web_sessions WHERE user_id=?',(ident,))
            self.shop.audit(db,'staff_access_changed',{'user_id':ident,'active':enabled,'owner_id':current['id']})
    def password(self,data):
        ident=int(data['id']);password=str(data.get('password',''))
        if not 12<=len(password)<=256:raise ValueError('Use a password of 12 to 256 characters.')
        salt,digest=password_hash(password)
        with self.shop.lock,self.shop.connect() as db:
            if not db.execute('SELECT 1 FROM web_users WHERE id=?',(ident,)).fetchone():raise ValueError('Account not found.')
            db.execute('UPDATE web_users SET salt=?,password_hash=? WHERE id=?',(salt,digest,ident));db.execute('DELETE FROM web_sessions WHERE user_id=?',(ident,))
            self.shop.audit(db,'staff_password_reset',{'user_id':ident})
