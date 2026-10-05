"""Authenticated single-business event sync; desktop credentials never enter SQLite."""
import datetime as dt
import hashlib
import json
import math
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from notifications import protect

TABLES=('products','parties','devices','stocks','allocations','recipes','documents','lines','movements','payments','expenses')
BUSINESS=('name','address','phone','gstin','state','gst_enabled','invoice_prefix','demo','admin_device_id')
DDL='''CREATE TABLE IF NOT EXISTS cloud_codes(digest TEXT PRIMARY KEY,expires REAL,location TEXT,percentage INTEGER,used_device TEXT);
CREATE TABLE IF NOT EXISTS cloud_peers(device_id TEXT PRIMARY KEY,token_hash TEXT,name TEXT,location TEXT,active INTEGER DEFAULT 1,last_contact TEXT);
CREATE TABLE IF NOT EXISTS cloud_stream(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS cloud_sent(event_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS cloud_inbox(seq INTEGER PRIMARY KEY,event TEXT);
'''
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def credential_file(shop):return shop.folder/'cloud-credential.bin'
def save_credential(shop,data):
    file=credential_file(shop);tmp=file.with_suffix('.tmp');tmp.touch(mode=0o600,exist_ok=True)
    tmp.write_bytes(protect(json.dumps(data).encode()));tmp.replace(file)
def credential(shop):
    file=credential_file(shop)
    return json.loads(protect(file.read_bytes(),decrypt=True)) if file.exists() else {}
def origin(value):
    p=urlparse(str(value).strip().rstrip('/'))
    local=p.scheme=='http' and p.hostname in ('localhost','127.0.0.1')
    if (p.scheme!='https' and not local) or not p.netloc or p.username or p.password or p.query or p.fragment or p.path:
        raise ValueError('Enter the server HTTPS address only, without a path, password or query.')
    return p.geturl()
def request(url,path,data,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(url+path,data=json.dumps(data).encode(),headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            raw=response.read(16000001)
            if len(raw)>16000000:raise ValueError('Sync response exceeds the review size limit.')
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        # Never include request URLs, authorization headers or response secrets in errors.
        if e.code in (401,403):raise ValueError('Server pairing expired or this PC was disabled. Review Offline PCs on the server.') from None
        raise ValueError('Server rejected the sync request (HTTP '+str(e.code)+').') from None
    except (urllib.error.URLError,TimeoutError,OSError):
        raise ValueError('Server unavailable. Saved bills remain on this PC; retry when connected.') from None

class Hub:
    def __init__(self,shop):
        self.shop=shop
        with shop.connect() as db:
            db.executescript(DDL)
            if not shop.settings(db).get('cloud_business_id'):
                db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('cloud_business_id',json.dumps(secrets.token_hex(16))))
    def index(self,db):
        db.execute('INSERT OR IGNORE INTO cloud_stream(event_id) SELECT id FROM sync_events ORDER BY date,id')
    def code(self,location,percentage):
        if location not in ('Warehouse','Outlet') or int(percentage) not in (0,25,50,100):raise ValueError('Choose location and stock allowance percentage.')
        with self.shop.lock,self.shop.connect() as db:
            s=self.shop.settings(db)
            if s['admin_device_id'] and s['admin_device_id']!=s['device_id']:raise ValueError('This server is not the stock authority.')
            if not s['admin_device_id']:
                before=self.shop.capture(db)
                db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(s['device_id']),'admin_device_id'))
                db.execute('INSERT OR IGNORE INTO devices VALUES(?,?,?)',(s['device_id'],'Online server','Warehouse'))
                self.shop.record_event(db,before)
            code=secrets.token_urlsafe(30)
            db.execute('DELETE FROM cloud_codes WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO cloud_codes VALUES(?,?,?,?,NULL)',(digest(code),time.time()+600,location,int(percentage)))
            return {'code':code,'expires_minutes':10,'location':location,'percentage':int(percentage)}
    def pair(self,data):
        ident=str(data.get('device_id',''));name=str(data.get('name','')).strip()[:100]
        if not re.fullmatch(r'[0-9a-f]{16}',ident) or not name:raise ValueError('A valid PC identity and name are required.')
        code=str(data.get('code',''));key=digest('alhidaya-device:'+code+':'+ident)
        with self.shop.lock,self.shop.connect() as db:
            c=db.execute('SELECT * FROM cloud_codes WHERE digest=? AND expires>?',(digest(code),time.time())).fetchone()
            if not c or (c['used_device'] and c['used_device']!=ident):raise PermissionError('Pairing code expired or already used.')
            peer=db.execute('SELECT * FROM cloud_peers WHERE device_id=?',(ident,)).fetchone()
            if peer and (not peer['active'] or peer['token_hash']!=digest(key)):raise PermissionError('This PC is already paired. Sync it or use a new PC identity.')
            if not peer:
                before=self.shop.capture(db)
                db.execute('INSERT INTO devices(id,name,location) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,location=excluded.location',(ident,name,c['location']))
                db.execute('INSERT INTO cloud_peers VALUES(?,?,?,?,1,?)',(ident,digest(key),name,c['location'],dt.datetime.now(dt.timezone.utc).isoformat()))
                for row in db.execute("SELECT s.product_id,s.quantity,p.kind FROM stocks s JOIN products p ON p.id=s.product_id WHERE s.location=?",(c['location'],)).fetchall():
                    reserved=db.execute('SELECT COALESCE(SUM(quantity),0) FROM allocations WHERE product_id=? AND location=?',(row['product_id'],c['location'])).fetchone()[0]
                    available=max(0,row['quantity']-reserved)
                    quantity=round(available*c['percentage']/100,6)
                    if row['kind']=='stock':quantity=float(math.floor(quantity))
                    if quantity>0:db.execute('INSERT INTO allocations VALUES(?,?,?,?)',(ident,row['product_id'],c['location'],quantity))
                self.shop.record_event(db,before)
            db.execute('UPDATE cloud_codes SET used_device=? WHERE digest=?',(ident,digest(code)))
            self.index(db)
            state={t:[dict(r) for r in db.execute('SELECT * FROM '+t)] for t in TABLES}
            state['settings']={k:v for k,v in self.shop.settings(db).items() if k in BUSINESS}
            state['seen']=[r['id'] for r in db.execute('SELECT id FROM sync_seen')]
            state['versions']=[dict(r) for r in db.execute('SELECT * FROM sync_versions')]
            return {'token':key,'business_id':self.shop.settings(db)['cloud_business_id'],'location':c['location'],'snapshot':state,'cursor':db.execute('SELECT COALESCE(MAX(seq),0) FROM cloud_stream').fetchone()[0]}
    def peer(self,db,token):
        row=db.execute('SELECT * FROM cloud_peers WHERE token_hash=? AND active=1',(digest(token),)).fetchone()
        if not row:raise PermissionError('PC connection disabled or unknown.')
        return row
    def validate(self,db,event,peer):
        ident=peer['device_id'];loc=peer['location']
        if event.get('version')!=1 or event.get('device')!=ident or not re.fullmatch(r'[0-9]{20}-'+ident+r'-[0-9a-f]{8}',event.get('id','')):raise ValueError('Invalid event identity.')
        p=event['payload']
        if p.get('settings') or p.get('recipes') or p['masters'].get('products') or p['append'].get('payments') or p['deltas'].get('parties'):raise ValueError('Offline tills cannot change shared stock administration, prices or credit ledgers.')
        for row in p['masters'].get('devices',[]):
            if row['id']!=ident or row['location']!=loc:raise ValueError('PC location is fixed by its pairing.')
        for row in p['masters'].get('parties',[]):
            old=db.execute('SELECT kind,credit_limit FROM parties WHERE id=?',(row['id'],)).fetchone()
            if row['kind']!='customer' or (old and old['kind']!='customer') or row.get('credit_limit',0)!=(old['credit_limit'] if old else 0):raise ValueError('Only customer profiles without credit changes can sync from a till.')
        reversed_any=False
        documents={}
        for row in p['masters'].get('documents',[]):
            documents[row['id']]=row
            if any(type(row[k]) is not int or row[k]<0 for k in ('total','paid','tax','discount')) or row['tax']>row['total'] or row['reversed'] not in (0,1):raise ValueError('Invalid invoice amounts.')
            snapshot=json.loads(row['snapshot']);old=db.execute('SELECT * FROM documents WHERE id=?',(row['id'],)).fetchone()
            if row['kind']!='sale' or row['location']!=loc or snapshot.get('device_id')!=ident or row['paid']!=row['total']:raise ValueError('Offline tills sync fully paid sales at their assigned location only.')
            if old:
                comparable=dict(old)
                comparable.pop('reversed',None)
                changed={k:v for k,v in row.items() if k!='reversed'}
                if comparable!=changed or old['reversed'] or not row['reversed']:raise ValueError('Issued invoices are immutable; only the issuing PC may reverse an unreversed bill.')
                reversed_any=True
        stock_deltas={}
        for r in p['deltas']['stocks']:
            if r['location']!=loc:raise ValueError('Stock belongs to another location.')
            stock_deltas[r['product_id']]=stock_deltas.get(r['product_id'],0)+r['delta']
        allocations={}
        for r in p['deltas'].get('allocations',[]):
            if r['device_id']!=ident or r['location']!=loc:raise ValueError('A till cannot change another PC allowance.')
            allocations[r['product_id']]=allocations.get(r['product_id'],0)+r['delta']
        for pid in set(stock_deltas)|set(allocations):
            ds=stock_deltas.get(pid,0);da=allocations.get(pid,0)
            if not math.isfinite(ds) or not math.isfinite(da):raise ValueError('Invalid stock quantities.')
            if ds and abs(ds-da)>0.000001:raise ValueError('Stock consumption must use this PC’s reserved allowance.')
            if (ds>0 or da>0) and not reversed_any:raise ValueError('Only a valid sale reversal can restore a till allowance.')
        movement_deltas={};reversal_deltas={}
        for row in p['append'].get('movements',[]):
            if row['location']!=loc:raise ValueError('Movement belongs to another location.')
            reference=row['reference'];document_id=reference[4:] if reference.startswith('REV-') else reference
            if document_id not in documents:raise ValueError('Movement must belong to this event’s invoice.')
            q=row['quantity']
            if documents[document_id]['reversed']:
                key=(document_id,row['product_id'])
                reversal_deltas[key]=reversal_deltas.get(key,0)+q
            if not math.isfinite(q) or (q>0)!=bool(documents[document_id]['reversed']):raise ValueError('Movement direction must match sale or reversal.')
            movement_deltas[row['product_id']]=movement_deltas.get(row['product_id'],0)+q
        for (document_id,pid),quantity in reversal_deltas.items():
            original=db.execute('SELECT COALESCE(SUM(quantity),0) FROM movements WHERE reference=? AND product_id=? AND location=?',(document_id,pid,loc)).fetchone()[0]
            if abs(quantity+original)>0.000001:raise ValueError('Reversal must restore the original stock consumption.')
        for pid in set(stock_deltas)|set(movement_deltas):
            if abs(stock_deltas.get(pid,0)-movement_deltas.get(pid,0))>0.000001:raise ValueError('Stock movement and balance must agree.')
        for row in p['append'].get('lines',[]):
            if row['document_id'] not in documents or documents[row['document_id']]['reversed']:raise ValueError('Lines belong to a new sale in this event.')
        for row in p['append'].get('expenses',[]):
            if type(row['amount']) is not int or row['amount']<=0 or row['method'] not in ('Cash','UPI','Card','Bank'):raise ValueError('Invalid expense.')
        if stock_deltas and not p['masters'].get('documents'):raise ValueError('Stock movements require a sale or reversal.')
    def exchange(self,token,data):
        events=data.get('events',[])
        if not isinstance(events,list) or len(events)>50:raise ValueError('Sync up to 50 events per request.')
        accepted=[];errors=[]
        with self.shop.lock:
            with self.shop.connect() as db:
                peer=dict(self.peer(db,token));business=self.shop.settings(db)['cloud_business_id']
                if data.get('business_id')!=business:raise PermissionError('Business identity does not match this PC.')
            for event in events:
                try:
                    with self.shop.connect() as db:
                        if db.execute('SELECT 1 FROM sync_seen WHERE id=?',(event.get('id'),)).fetchone():
                            accepted.append(event['id']);continue
                        self.validate(db,event,peer)
                        self.shop.apply_event(db,event)
                        for row in db.execute('SELECT product_id,location,SUM(quantity) AS total FROM allocations GROUP BY product_id,location'):
                            physical=db.execute('SELECT quantity FROM stocks WHERE product_id=? AND location=?',(row['product_id'],row['location'])).fetchone()
                            if not physical or row['total']>physical[0]+0.000001:raise ValueError('Stock allowances exceed physical stock.')
                        db.execute('INSERT INTO sync_events VALUES(?,?,?,?)',(event['id'],event['date'],event['device'],json.dumps(event['payload'])))
                        accepted.append(event['id'])
                except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:
                    errors.append({'id':event.get('id','invalid'),'message':str(e)[:200]})
            with self.shop.connect() as db:
                self.index(db)
                db.execute('UPDATE cloud_peers SET last_contact=? WHERE device_id=?',(dt.datetime.now(dt.timezone.utc).isoformat(),peer['device_id']))
                cursor=int(data.get('cursor',0));rows=db.execute('SELECT s.seq,e.* FROM cloud_stream s JOIN sync_events e ON e.id=s.event_id WHERE s.seq>? ORDER BY s.seq LIMIT 50',(cursor,)).fetchall()
                outgoing=[{'seq':r['seq'],'event':{'version':1,'id':r['id'],'date':r['date'],'device':r['device'],'payload':json.loads(r['payload'])}} for r in rows]
                return {'business_id':business,'accepted':accepted,'errors':errors,'events':outgoing,'cursor':rows[-1]['seq'] if rows else cursor,'more':len(rows)==50}

def pair_desktop(shop,data):
    with shop.cloud_lock,shop.lock:
        return _pair_desktop(shop,data)

def _pair_desktop(shop,data):
    url=origin(data.get('url',''))
    with shop.lock,shop.connect() as db:
        db.executescript(DDL);s=shop.settings(db)
        if s.get('cloud_url'):raise ValueError('This PC is already paired. Use Sync now; preserve any unsent bills before changing servers.')
        populated=db.execute('SELECT 1 FROM products').fetchone() or db.execute('SELECT 1 FROM documents').fetchone()
        if populated and not data.get('replace_sample'):raise ValueError('Back up and explicitly confirm replacement of this PC’s sample records. Real-data migration is not available in this join flow.')
        ident=s['device_id'];name=str(data.get('name') or s['device_name'] or 'Offline till').strip()
    # Retain the existing records before any network request or replacement.
    shop.backup(local_only=True)
    reply=request(url,'/api/device-pair',{'device_id':ident,'name':name,'code':str(data.get('code',''))})
    state=reply['snapshot']
    with shop.lock,shop.connect() as db:
        db.execute('DELETE FROM notifications')
        for t in reversed(TABLES):db.execute('DELETE FROM '+t)
        for t in TABLES:
            allowed={r[1] for r in db.execute('PRAGMA table_info('+t+')')}
            for row in state[t]:
                if set(row)!=allowed:raise ValueError('The server requires a compatible app version.')
                cols=list(row);db.execute('INSERT INTO '+t+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',tuple(row.values()))
        for t in ('sync_events','sync_seen','sync_versions','sync_errors','cloud_sent','cloud_inbox'):db.execute('DELETE FROM '+t)
        db.executemany('INSERT INTO sync_seen VALUES(?)',[(eid,) for eid in state['seen']])
        db.executemany('INSERT INTO sync_versions VALUES(?,?)',[(r['entity'],r['version']) for r in state['versions']])
        for key,value in {**state['settings'],'cloud_url':url,'cloud_business_id':reply['business_id'],'cloud_cursor':reply['cursor'],'device_location':reply['location'],'device_name':name,'setup_role':'join','sync_folder':'','whatsapp_enabled':False}.items():
            db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
        save_credential(shop,{'token':reply['token'],'business_id':reply['business_id']})
    return {'message':'PC paired. Server records loaded after a local backup. Offline sales use this PC’s allowance.'}

def sync_desktop(shop):
    with shop.cloud_lock:
        return _sync_desktop(shop)

def _sync_desktop(shop):
    with shop.lock,shop.connect() as db:
        db.executescript(DDL);s=shop.settings(db);key=credential(shop)
        if not key.get('token'):raise ValueError('This PC has no connection credential. Review pairing before billing.')
        rows=db.execute('SELECT * FROM sync_events WHERE id NOT IN (SELECT event_id FROM cloud_sent) ORDER BY date,id LIMIT 50').fetchall()
        events=[{'version':1,'id':r['id'],'device':r['device'],'date':r['date'],'payload':json.loads(r['payload'])} for r in rows]
    reply=request(s['cloud_url'],'/api/device-sync',{'business_id':s['cloud_business_id'],'events':events,'cursor':s.get('cloud_cursor',0)},key['token'])
    if reply['business_id']!=s['cloud_business_id']:raise ValueError('Server business identity changed. No records were imported.')
    with shop.lock,shop.connect() as db:
        db.executemany('INSERT OR IGNORE INTO cloud_sent VALUES(?)',[(eid,) for eid in reply['accepted']])
        for error in reply['errors']:db.execute('INSERT OR REPLACE INTO sync_errors VALUES(?,?)',(error['id'],error['message']))
        for event in reply['events']:db.execute('INSERT OR IGNORE INTO cloud_inbox VALUES(?,?)',(event['seq'],json.dumps(event['event'])))
        db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('cloud_cursor',json.dumps(reply['cursor'])))
    imported=0
    for _ in range(3):
        with shop.connect() as db:pending=[dict(r) for r in db.execute('SELECT * FROM cloud_inbox ORDER BY seq')]
        progress=0
        for row in pending:
            event=json.loads(row['event'])
            try:
                with shop.lock,shop.connect() as db:
                    if shop.apply_event(db,event):imported+=1
                    db.execute('DELETE FROM cloud_inbox WHERE seq=?',(row['seq'],))
                    db.execute('DELETE FROM sync_errors WHERE id=?',(event['id'],))
                progress+=1
            except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:
                with shop.connect() as db:db.execute('INSERT OR REPLACE INTO sync_errors VALUES(?,?)',(event['id'],str(e)[:200]))
        if not progress:break
    with shop.connect() as db:
        remaining=db.execute('SELECT COUNT(*) FROM sync_events WHERE id NOT IN (SELECT event_id FROM cloud_sent)').fetchone()[0]
        waiting=db.execute('SELECT COUNT(*) FROM cloud_inbox').fetchone()[0]
        stamp=dt.datetime.now().astimezone().isoformat(timespec='seconds')
        db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('last_sync',json.dumps(stamp)))
    return {'imported':imported,'pending':remaining+waiting,'more':reply['more'] or remaining>0,'message':f'{imported} server events imported; {remaining+waiting} awaiting exchange or review.'}
