"""Temporary single-business web review server. TLS terminates at Caddy on localhost."""
import argparse
import hashlib
import hmac
import html
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Shop,ROOT

ROLES={'owner','manager','cashier','viewer'}
MANAGER={'product','party','recipe','purchase','payment','expense','transfer','adjust','reverse','import_products','sale','trade_order_status','trade_order_reprice'}
CASHIER={'sale','party','expense'}
SETTINGS={'name','address','phone','gstin','state','gst_enabled','invoice_prefix','printer'}
def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt,hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()

class Online:
    def __init__(self,folder,origin,secure=True):
        self.shop=Shop(folder);self.origin=origin.rstrip('/');self.secure=secure
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
        if len(password)<12:raise ValueError('Use a password of at least 12 characters.')
        salt,digest=password_hash(password)
        with self.shop.lock,self.shop.connect() as db:
            db.execute('INSERT INTO web_users(username,name,role,location,salt,password_hash) VALUES(?,?,?,?,?,?)',(name,str(data.get('name') or name),role,location,salt,digest))
    def login(self,username,password,ip):
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
        for key in ('sync_folder','backup_folder','last_backup','last_sync'):s[key]=''
        result['local']=False;result['online']=True;result['web_user']={k:user[k] for k in ('username','name','role','location')}
        s['device_location']=user['location']
        if user['role']!='owner':
            result['whatsapp_sessions']=[];result['commerce_products']=[];result['media_assets']=[];result['catalogue_products']=[];result['catalogue_orders']=[];result['internal_contacts']=[];result['notifications']=[];result['campaigns']=[];result['whatsapp_templates']=[];result['whatsapp_webhook_configured']=False;result['whatsapp_token_configured']=False
            for key in tuple(s):
                if key.startswith('whatsapp_'):s[key]=False if isinstance(s[key],bool) else ''
            result['devices']=[];result['allocations']=[];result['sync_errors']=[]
        if user['role'] in ('cashier','viewer'):
            result['trade_orders']=[]
            result['stocks']=[r for r in result['stocks'] if r['location']==user['location']]
            for p in result['products']:
                p['stock']=sum(r['quantity'] for r in result['stocks'] if r['product_id']==p['id'])
                p['cost']=0
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
        if action in ('sync','shutdown','cloud_pair','cloud_address'):
            raise ValueError('This local-device operation is unavailable in the hosted review.')
        if action=='settings':data={k:v for k,v in data.items() if k in SETTINGS}
        if role in ('manager','cashier'):
            if action in ('sale','purchase','expense','adjust','product'):data['location']=user['location']
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
        with self.shop.connect() as db:db.execute('INSERT INTO web_audit(created,user_id,action) VALUES(?,?,?)',(time.time(),user['id'],action))
        return result

LOGIN='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Al Hadiya · Staff sign in</title><link rel="stylesheet" href="/style.css"><body style="display:grid;place-items:center;min-height:100vh;background:#f6f6ef"><main class="card" style="max-width:430px;padding:36px;margin:20px"><div class="eyebrow">AL HADIYA TRADERS</div><h1>Welcome back.</h1><p>Sign in to your business workspace.</p><form method="post" action="/login"><label>Username</label><input name="username" autocomplete="username" required><label>Password</label><input type="password" name="password" autocomplete="current-password" required><button class="btn gold" style="margin-top:24px;width:100%">Sign in</button></form><p style="color:#ac3333">{error}</p><small>Temporary review · use test data only.</small><p><a href="/">← Visit our website</a></p></main></body></html>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    @property
    def online(self):return self.server.online
    def send(self,status,body,mime='application/json',headers=None):
        raw=json.dumps(body).encode() if mime=='application/json' else body.encode() if isinstance(body,str) else body
        self.send_response(status)
        for k,v in {'Content-Type':mime,'Content-Length':str(len(raw)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin',**(headers or {})}.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(raw)
    def redirect(self,path,cookie=None):self.send(303,b'','text/plain',{'Location':path,**({'Set-Cookie':cookie} if cookie else {})})
    def do_GET(self):
        path=urlparse(self.path).path;user=self.online.session(self.headers.get('Cookie'))
        if path=='/':return self.send(200,(ROOT/'marketing/index.html').read_bytes(),'text/html; charset=utf-8')
        if path in ('/privacy','/data-deletion'):return self.send(200,(ROOT/'marketing'/(path[1:]+'.html')).read_bytes(),'text/html; charset=utf-8')
        if path=='/login':return self.send(200,LOGIN.format(error=''),'text/html; charset=utf-8')
        if path=='/catalogue':return self.send(200,(ROOT/'marketing/catalogue.html').read_bytes(),'text/html; charset=utf-8')
        if path=='/api/catalogue':
            from media_catalogue import public_state
            return self.send(200,public_state(self.online.shop))
        if path.startswith('/media/'):
            from media_catalogue import public_asset,asset_path
            try:
                ident=path[7:]
                with self.online.shop.connect() as db:r=db.execute('SELECT mime FROM media_assets WHERE id=?',(ident,)).fetchone()
                if not r or (not user and not public_asset(self.online.shop,ident)):return self.send(404,{'error':'Image not found.'})
                return self.send(200,asset_path(self.online.shop,ident).read_bytes(),r['mime'])
            except (ValueError,OSError):return self.send(404,{'error':'Image not found.'})
        if path=='/health':return self.send(200,{'status':'ok'})
        if path=='/webhooks/whatsapp':
            from outreach import challenge
            try:return self.send(200,challenge(self.online.shop,parse_qs(urlparse(self.path).query)),'text/plain')
            except PermissionError:return self.send(403,{'error':'Webhook verification failed.'})
        downloads={'/downloads/AlHidayaTraders-Setup-0.7.0.exe':'application/octet-stream','/downloads/SHA256SUMS.txt':'text/plain','/downloads/AlHidayaTraders-source-0.7.0.zip':'application/zip'}
        if path in downloads:
            file=ROOT/'dist'/Path(path).name
            if not file.is_file():return self.send(404,{'error':'Download is being prepared.'})
            return self.send(200,file.read_bytes(),downloads[path],{'Content-Disposition':'attachment; filename="'+file.name+'"'})
        if path=='/style.css':return self.send(200,(ROOT/'static/style.css').read_bytes(),'text/css')
        if not user:
            return self.send(401,{'error':'Sign in again.'}) if path.startswith('/api/') else self.redirect('/login')
        if path=='/api/session':return self.send(200,{'token':user['csrf']})
        if path=='/api/state':return self.send(200,self.online.state(user))
        if path=='/api/peers':
            if user['role']!='owner':return self.send(403,{'error':'Owner permission required.'})
            with self.online.shop.connect() as db:rows=[dict(r) for r in db.execute('SELECT device_id,name,location,active,last_contact FROM cloud_peers')]
            return self.send(200,rows)
        if path=='/api/users':
            if user['role']!='owner':return self.send(403,{'error':'Owner permission required.'})
            with self.online.shop.connect() as db:rows=[dict(r) for r in db.execute('SELECT id,username,name,role,location,active FROM web_users')]
            return self.send(200,rows)
        if path=='/api/commerce-feed':
            if user['role']!='owner':return self.send(403,{'error':'Owner permission required.'})
            from whatsapp_orders import feed
            try:return self.send(200,feed(self.online.shop,self.online.origin),'text/csv; charset=utf-8',{'Content-Disposition':'attachment; filename=al-hadiya-commerce.csv'})
            except ValueError as e:return self.send(400,{'error':str(e)})
        if path=='/api/backup-download':
            if user['role']!='owner':return self.send(403,{'error':'Owner permission required.'})
            file=Path(self.online.shop.backup(local_only=True)['paths'][0])
            return self.send(200,file.read_bytes(),'application/vnd.sqlite3')
        if path=='/app':
            markup=(ROOT/'static/index.html').read_text().replace('Offline billing ready','Online review').replace('Your data stays on this PC','Shared test workspace').replace('↻ Sync transactions','Account & staff').replace('onclick="runSync()"','onclick="navTo(\'staff\')"').replace('Local SQLite storage','Temporary review server').replace('<script src="/app.js"></script>','<script src="/app.js"></script><script src="/cloud-ui.js"></script>')
            return self.send(200,markup,'text/html; charset=utf-8')
        files={'/app.js':ROOT/'static/app.js','/cloud-ui.js':ROOT/'cloud/ui.js'}
        if path in files:return self.send(200,files[path].read_bytes(),'text/javascript')
        self.send(404,{'error':'Not found'})
    def do_POST(self):
        path=urlparse(self.path).path
        device_request=path in ('/api/device-pair','/api/device-sync')
        if not device_request and path!='/webhooks/whatsapp' and self.headers.get('Origin')!=self.online.origin:return self.send(403,{'error':'Origin rejected.'})
        try:
            self.connection.settimeout(15)
            if self.headers.get('Transfer-Encoding','').lower()=='chunked':
                chunks=[];size=0
                while True:
                    line=self.rfile.readline(128)
                    if not line.endswith(b'\r\n'):raise ValueError('Invalid request encoding.')
                    length=int(line.split(b';')[0].strip(),16)
                    if length<0 or size+length>8000000:raise ValueError('Request too large.')
                    if not length:
                        if self.rfile.readline(8192)!=b'\r\n':raise ValueError('Request trailers are not accepted.')
                        break
                    chunk=self.rfile.read(length)
                    if len(chunk)!=length or self.rfile.read(2)!=b'\r\n':raise ValueError('Incomplete request.')
                    chunks.append(chunk);size+=length
                raw=b''.join(chunks)
            else:
                size=int(self.headers.get('Content-Length',0))
                if size<1 or size>8000000:raise ValueError('Invalid request size.')
                raw=self.rfile.read(size)
                if len(raw)!=size:raise ValueError('Incomplete request.')
            if path=='/webhooks/whatsapp':
                from outreach import receive
                if len(raw)>1000000:raise ValueError('Webhook too large.')
                return self.send(200,receive(self.online.shop,raw,self.headers.get('X-Hub-Signature-256','')))
            if path=='/api/catalogue-order':
                from media_catalogue import order
                if len(raw)>16000:raise ValueError('Order request too large.')
                ip=self.headers.get('X-Forwarded-For',self.client_address[0]).split(',')[0]
                with self.online.lock:
                    attempts=[t for t in self.online.order_attempts.get(ip,[]) if time.time()-t<3600]
                    if len(attempts)>=6:return self.send(429,{'error':'Too many order requests. Please contact the shop.'})
                    if len(self.online.order_attempts)>10000:self.online.order_attempts={}
                    self.online.order_attempts[ip]=attempts+[time.time()]
                return self.send(200,order(self.online.shop,json.loads(raw)))
            if device_request:
                data=json.loads(raw)
                if path=='/api/device-pair':return self.send(200,self.online.hub.pair(data))
                authorization=self.headers.get('Authorization','')
                if not authorization.startswith('Bearer '):raise PermissionError('A paired PC credential is required.')
                return self.send(200,self.online.hub.exchange(authorization[7:],data))
            if path=='/login':
                fields=parse_qs(raw.decode());ip=self.headers.get('X-Forwarded-For',self.client_address[0]).split(',')[0]
                token=self.online.login(fields.get('username',[''])[0],fields.get('password',[''])[0],ip)
                if not token:return self.send(401,LOGIN.format(error='Unable to sign in. Check your details or wait a minute.'),'text/html; charset=utf-8')
                return self.redirect('/app','ah_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=14400'+('; Secure' if self.online.secure else ''))
            user=self.online.session(self.headers.get('Cookie'))
            if not user:return self.send(401,{'error':'Sign in again.'})
            if not hmac.compare_digest(self.headers.get('X-Shop-Token',''),user['csrf']):return self.send(403,{'error':'Session verification failed.'})
            data=json.loads(raw)
            if path=='/api/logout':
                with self.online.shop.connect() as db:db.execute('DELETE FROM web_sessions WHERE digest=?',(user['digest'],))
                return self.send(200,{'ok':True},headers={'Set-Cookie':'ah_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+('; Secure' if self.online.secure else '')})
            if path=='/api/pair-code':
                if user['role']!='owner':raise PermissionError('Owner permission required.')
                return self.send(200,self.online.hub.code(data.get('location'),data.get('percentage',50)))
            if path in ('/api/peer-disable','/api/peer-enable'):
                if user['role']!='owner':raise PermissionError('Owner permission required.')
                with self.online.shop.connect() as db:db.execute('UPDATE cloud_peers SET active=? WHERE device_id=?',(int(path.endswith('peer-enable')),data.get('device_id')))
                return self.send(200,{'message':'Sync enabled again.' if path.endswith('peer-enable') else 'Sync disabled. Saved records remain on this node; enable sync to exchange them again.'})
            if path=='/api/location':
                if user['role']!='owner':raise PermissionError('Only owners can switch review locations.')
                if data.get('location') not in ('Warehouse','Outlet'):raise ValueError('Choose a valid location.')
                with self.online.shop.connect() as db:db.execute('UPDATE web_users SET location=? WHERE id=?',(data['location'],user['id']))
                return self.send(200,{'ok':True})
            if path=='/api/staff_user':
                if user['role']!='owner':raise PermissionError('Owner permission required.')
                self.online.user(data);return self.send(200,{'ok':True})
            if path=='/api/staff_disable':
                if user['role']!='owner':raise PermissionError('Owner permission required.')
                if int(data['id'])==user['id']:raise ValueError('You cannot disable your current owner account.')
                with self.online.shop.connect() as db:
                    db.execute('UPDATE web_users SET active=0 WHERE id=?',(int(data['id']),));db.execute('DELETE FROM web_sessions WHERE user_id=?',(int(data['id']),))
                return self.send(200,{'ok':True})
            if not path.startswith('/api/'):return self.send(404,{'error':'Not found'})
            self.send(200,self.online.act(user,path[5:],data))
        except PermissionError as e:self.send(403,{'error':str(e)})
        except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:self.send(400,{'error':str(e)})
        except Exception:self.send(500,{'error':'Operation failed. No credentials or internal details are returned.'})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True);parser.add_argument('--origin',required=True);parser.add_argument('--port',type=int,default=8767);parser.add_argument('--bootstrap',type=Path);parser.add_argument('--demo',action='store_true');args=parser.parse_args()
    online=Online(args.data_dir,args.origin,args.origin.startswith('https://'))
    if args.bootstrap:
        with online.shop.connect() as db:exists=db.execute('SELECT 1 FROM web_users').fetchone()
        if not exists:
            data=json.loads(args.bootstrap.read_text())
            if 'password_hash' in data:
                with online.shop.connect() as db:db.execute('INSERT INTO web_users(username,name,role,location,salt,password_hash) VALUES(?,?,?,?,?,?)',(data['username'],'Owner','owner','Warehouse',data['salt'],data['password_hash']))
            else:online.user(data)
        args.bootstrap.unlink(missing_ok=True)
    with online.shop.connect() as db:empty=not db.execute('SELECT 1 FROM products').fetchone()
    if empty and args.demo:online.shop.act('demo',{})
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);server.online=online
    def periodic():
        last_backup=last_templates=0
        while True:
            time.sleep(10)
            try:
                if time.time()-last_backup>=300:
                    online.shop.backup(local_only=True);last_backup=time.time()
                    online.shop.daily_update()
                with online.shop.connect() as db:enabled=online.shop.settings(db)['whatsapp_enabled']
                if enabled and time.time()-last_templates>=600:
                    from outreach import refresh_templates
                    try:refresh_templates(online.shop)
                    except Exception:pass
                    last_templates=time.time()
                from notifications import process_outbox
                process_outbox(online.shop)
            except Exception:pass
    threading.Thread(target=periodic,daemon=True).start();server.serve_forever()
if __name__=='__main__':main()
