"""Authenticated loopback-only Windows HTTP adapter."""
import hashlib,hmac,html,json,threading
from http.cookies import SimpleCookie
from urllib.parse import parse_qs,urlparse
from app import Handler as Base,ROOT,TOKEN
from staff_access import StaffAccess

LOGIN='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/style.css"><body class="auth-screen"><main class="card auth-card"><div class="eyebrow">AL HADIYA TRADERS</div><h1>{title}</h1><p>{intro}</p><form method="post" action="{action}"><label for="login-username">Username</label><input id="login-username" autofocus name="username" autocomplete="username" required><label for="login-password">Password</label><input id="login-password" type="password" name="password" autocomplete="{autocomplete}" minlength="12" required><button class="btn gold" type="submit">{button}</button></form><p class="error">{error}</p><small>Your business records stay on this PC. Sign-in works offline.</small></main></body></html>'''
class DesktopHandler(Base):
 @property
 def access(self):return self.server.access
 def output(self,status,body,mime='application/json',headers=None):
  raw=json.dumps(body).encode() if mime=='application/json' else body.encode() if isinstance(body,str) else body
  self.send_response(status)
  for k,v in {'Content-Type':mime,'Content-Length':str(len(raw)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',**(headers or {})}.items():self.send_header(k,v)
  self.end_headers();self.wfile.write(raw)
 def redirect(self,path,cookie=None):return self.output(303,b'','text/plain',{'Location':path,**({'Set-Cookie':cookie} if cookie else {})})
 def first(self):
  with self.shop.connect() as db:return not db.execute('SELECT 1 FROM web_users').fetchone()
 def login_page(self,error=''):
  first=self.first();return LOGIN.format(title='Set up owner access' if first else 'Welcome back.',intro='Create the owner account for this PC. Use at least 12 characters.' if first else 'Sign in to your business workspace.',action='/setup' if first else '/login',autocomplete='new-password' if first else 'current-password',button='Create owner account' if first else 'Sign in',error=html.escape(error))
 def do_GET(self):
  if not self.valid_host():return self.output(403,{'error':'Local access only.'})
  path=urlparse(self.path).path
  if path=='/health':return self.output(200,{'local':True,'version':(ROOT/'VERSION').read_text().strip()})
  if path=='/style.css':return self.output(200,(ROOT/'static/style.css').read_bytes(),'text/css')
  if path in ('/login','/setup'):return self.output(200,self.login_page(),'text/html; charset=utf-8')
  user=self.access.session(self.headers.get('Cookie'))
  if not user:return self.output(401,{'error':'Sign in again.'}) if path.startswith('/api/') else self.redirect('/setup' if self.first() else '/login')
  if path=='/api/session':return self.output(200,{'token':user['csrf']})
  if path=='/api/state':return self.output(200,self.access.state(user))
  if path=='/api/users':
   if user['role']!='owner':return self.output(403,{'error':'Owner permission required.'})
   with self.shop.connect() as db:return self.output(200,[dict(r) for r in db.execute('SELECT id,username,name,role,location,active FROM web_users')])
  if path.startswith('/api/backup'):
   if user['role']!='owner':return self.output(403,{'error':'Owner permission required.'})
   if path=='/api/backup-bundle':return self.output(200,__import__('backup_bundle').bundle(self.shop),'application/zip',{'Content-Disposition':'attachment; filename=AlHadiya-business-backup.zip'})
  if path=='/team.js':return self.output(200,(ROOT/'static/team.js').read_bytes(),'text/javascript')
  if path=='/':return self.output(200,(ROOT/'static/index.html').read_text(encoding='utf-8').replace('</body>','<script src="/team.js"></script></body>'),'text/html; charset=utf-8')
  return super().do_GET()
 def do_POST(self):
  if not self.valid_host():return self.output(403,{'error':'Local access only.'})
  path=urlparse(self.path).path
  if path=='/api/shutdown' and hmac.compare_digest(self.headers.get('X-Shop-Token',''),TOKEN):return super().do_POST()
  origin=self.headers.get('Origin','')
  if origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):return self.output(403,{'error':'Origin rejected.'})
  try:
   size=int(self.headers.get('Content-Length',0));self.connection.settimeout(15)
   if not 0<size<=(90000000 if path=='/api/restore_bundle' else 8000000):raise ValueError('Invalid request size.')
   raw=self.rfile.read(size)
   if len(raw)!=size:raise ValueError('Incomplete request.')
   if path in ('/login','/setup'):
    fields={k:v[0] for k,v in parse_qs(raw.decode()).items()}
    if path=='/setup':
     with self.shop.lock:
      if not self.first():raise PermissionError('Owner setup is already complete.')
      self.access.user({**fields,'role':'owner','location':'Warehouse'})
    token=self.access.login(fields.get('username',''),fields.get('password',''),self.client_address[0])
    if not token:return self.output(401,self.login_page('Check your details, or wait one minute before retrying.'),'text/html; charset=utf-8')
    return self.redirect('/','ah_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=14400')
   user=self.access.session(self.headers.get('Cookie'))
   if not user:return self.output(401,{'error':'Sign in again.'})
   if not hmac.compare_digest(self.headers.get('X-Shop-Token',''),user['csrf']):raise PermissionError('Session verification failed.')
   data=json.loads(raw);action=path.removeprefix('/api/')
   if not path.startswith('/api/') or not isinstance(data,dict):raise ValueError('Invalid operation.')
   if action=='logout':
    with self.shop.connect() as db:db.execute('DELETE FROM web_sessions WHERE digest=?',(user['digest'],))
    return self.output(200,{'ok':True},headers={'Set-Cookie':'ah_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
   if action in ('staff_user','staff_disable','staff_enable','staff_password','restore_bundle','shutdown','location'):
    if user['role']!='owner':raise PermissionError('Owner permission required.')
    if action=='staff_user':self.access.user(data);return self.output(200,{'ok':True})
    if action=='staff_password':self.access.password(data);return self.output(200,{'ok':True})
    if action in ('staff_disable','staff_enable'):
     self.access.active(user,data['id'],action=='staff_enable');return self.output(200,{'ok':True})
    if action=='restore_bundle':return self.output(200,__import__('backup_bundle').restore(self.shop,data))
    if action=='location':
     location=self.shop.location(data['location'])
     with self.shop.connect() as db:db.execute('UPDATE web_users SET location=? WHERE id=?',(location,user['id']))
     self.shop.act('settings',{'device_location':location});return self.output(200,{'ok':True})
    if action=='shutdown':
     self.shop.backup(local_only=True);self.output(200,{'message':'Backup saved. App closed.'});threading.Thread(target=self.server.shutdown,daemon=True).start();return
   data={k:v for k,v in data.items() if not k.startswith('_request_')}
   data['_request_id']=self.headers.get('X-Request-ID','');data['_request_actor']=str(user['id'])+':'+user['role']
   return self.output(200,self.access.act(user,action,data))
  except PermissionError as e:return self.output(403,{'error':str(e)})
  except (ValueError,KeyError,TypeError) as e:return self.output(400,{'error':str(e)})
  except Exception:return self.output(500,{'error':'Operation could not finish. Review saved records before retrying.'})
