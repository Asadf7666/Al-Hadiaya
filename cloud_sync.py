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

TABLES=('products','parties','devices','stocks','allocations','recipes','documents','lines','movements','payments','expenses','commerce_products','trade_orders','inventory_plans','purchase_orders')
BUSINESS=('name','address','phone','gstin','state','gst_enabled','invoice_prefix','demo','admin_device_id','node_mode')
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
        try:message=json.loads(e.read(4096)).get('error','')
        except Exception:message=''
        raise ValueError(message[:300] or 'Server rejected the sync request (HTTP '+str(e.code)+').') from None
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
    def code(self,location,percentage=0):
        if location not in ('Warehouse','Outlet'):raise ValueError('Choose a default transaction location.')
        with self.shop.lock,self.shop.connect() as db:
            s=self.shop.settings(db)
            before=self.shop.capture(db)
            db.execute('INSERT OR IGNORE INTO devices VALUES(?,?,?)',(s['device_id'],'Online node','Warehouse'))
            self.shop.record_event(db,before)
            code=secrets.token_urlsafe(30)
            db.execute('DELETE FROM cloud_codes WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO cloud_codes VALUES(?,?,?,?,NULL)',(digest(code),time.time()+600,location,int(percentage)))
            return {'code':code,'expires_minutes':10,'location':location,'percentage':int(percentage)}
    def pair(self,data):
        if data.get('protocol')!=5:raise ValueError('Install Windows 0.8.0 or newer for full node operations.')
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
        ident=peer['device_id']
        if event.get('version')!=1 or event.get('device')!=ident or not re.fullmatch(r'[0-9]{20}-'+ident+r'-[0-9a-f]{8}',event.get('id','')):raise ValueError('Invalid event identity.')
        p=event['payload']
        if set(p)-{'masters','append','deltas','settings','recipes'}:raise ValueError('Unknown event content.')
        if set(p['masters'])-{'products','parties','devices','documents','commerce_products','trade_orders','inventory_plans','purchase_orders'} or set(p['append'])-{'lines','movements','payments','expenses'} or set(p['deltas'])-{'stocks','parties','allocations'}:raise ValueError('Unknown synced table.')
        for row in p['masters'].get('devices',[]):
            if row['id']!=ident or row['location'] not in ('Warehouse','Outlet'):raise ValueError('Only this node’s identity may be updated.')
        for row in p['settings']:
            if row['key'] not in BUSINESS or row['key']=='admin_device_id':raise ValueError('Invalid shared business setting.')
            if row['key']=='node_mode' and json.loads(row['value'])!='unified':raise ValueError('All nodes must use the same capabilities.')
        for row in p['masters'].get('products',[]):
            if row['kind'] not in ('stock','ingredient','recipe'):raise ValueError('Invalid product type.')
            for key in ('price','cost','mrp','wholesale_price'):
                if type(row[key]) is not int or row[key]<0:raise ValueError('Invalid product money amount.')
            for key in ('gst','cess','minimum','pack'):
                if not math.isfinite(row[key]) or row[key]<0:raise ValueError('Invalid product quantity or tax.')
            if row['gst']>100 or row['cess']>100 or row['pack']<1:raise ValueError('Invalid product tax or pack size.')
        for row in p['masters'].get('parties',[]):
            if row['kind'] not in ('customer','supplier') or type(row['credit_limit']) is not int or row['credit_limit']<0:raise ValueError('Invalid customer or supplier.')
            old=db.execute('SELECT kind FROM parties WHERE id=?',(row['id'],)).fetchone()
            if old and old['kind']!=row['kind']:raise ValueError('A customer or supplier cannot change type.')
        __import__('procurement').validate_receipts(p)
        for row in p['masters'].get('purchase_orders',[]):__import__('procurement').validate_change(db,row,p)
        for row in p['masters'].get('inventory_plans',[]):__import__('procurement').validate_plan(row)
        for table in ('commerce_products','trade_orders','inventory_plans','purchase_orders'):
            for row in p['masters'].get(table,[]):
                permitted={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
                if set(row)!=permitted:raise ValueError('Invalid synced order fields.')
                if table=='trade_orders':
                    from whatsapp_orders import STATUSES
                    if row['status'] not in STATUSES or row['location']!='Warehouse' or type(row['total']) is not int or row['total']<0 or row['contact_allowed'] not in (0,1):raise ValueError('Invalid trading order.')
                    if row['id']!='WA-'+hashlib.sha256(row['source_id'].encode()).hexdigest()[:12].upper():raise ValueError('Invalid WhatsApp order identity.')
                    items=json.loads(row['items'])
                    if not 1<=len(items)<=30 or any(type(l['quantity']) is not int or l['quantity']<1 or type(l['price']) is not int or l['price']<0 for l in items):raise ValueError('Invalid order lines.')
                    if sum(l['quantity']*l['price'] for l in items)!=row['total']:raise ValueError('Order total differs from lines.')
                    if row['invoice_id']:
                        doc=next((d for d in p['masters'].get('documents',[]) if d['id']==row['invoice_id']),None) or db.execute('SELECT * FROM documents WHERE id=?',(row['invoice_id'],)).fetchone()
                        if not doc or doc['kind']!='sale' or doc['total']!=row['total'] or doc['location']!='Warehouse' or json.loads(doc['snapshot']).get('trade_order_id')!=row['id']:raise ValueError('Order must reference a valid matching sale invoice.')
                elif type(row['units']) is not int or not 1<=row['units']<=1000 or row['price_tier'] not in ('retail','wholesale') or row['active'] not in (0,1):raise ValueError('Invalid catalogue mapping.')
        documents={};ledger={}
        for row in p['masters'].get('documents',[]):
            documents[row['id']]=row
            if any(type(row[k]) is not int or row[k]<0 for k in ('total','paid','tax','discount')) or row['tax']>row['total'] or row['paid']>row['total'] or row['reversed'] not in (0,1):raise ValueError('Invalid invoice amounts.')
            if row['kind'] not in ('sale','purchase') or row['location'] not in ('Warehouse','Outlet'):raise ValueError('Invalid invoice type or location.')
            snapshot=json.loads(row['snapshot']);old=db.execute('SELECT * FROM documents WHERE id=?',(row['id'],)).fetchone()
            if old:
                if {k:v for k,v in dict(old).items() if k!='reversed'}!={k:v for k,v in row.items() if k!='reversed'} or old['reversed'] or not row['reversed']:raise ValueError('Invoice is immutable or already reversed on another node.')
            elif snapshot.get('device_id')!=ident or row['reversed']:raise ValueError('A new invoice must identify this node.')
            if row['party_id']:
                ledger[row['party_id']]=ledger.get(row['party_id'],0)+(row['total']-row['paid'])*(-1 if row['reversed'] else 1)
            elif row['paid']!=row['total']:raise ValueError('Credit requires a customer or supplier.')
        for row in p['append'].get('payments',[]):
            if type(row['amount']) is not int or row['amount']<=0 or row['method'] not in ('Cash','UPI','Card','Bank'):raise ValueError('Invalid payment.')
            ledger[row['party_id']]=ledger.get(row['party_id'],0)-row['amount']
        deltas={}
        for row in p['deltas']['parties']:
            if type(row['delta']) is not int:raise ValueError('Invalid ledger delta.')
            deltas[row['id']]=deltas.get(row['id'],0)+row['delta']
        if {k:v for k,v in ledger.items() if v}!={k:v for k,v in deltas.items() if v}:raise ValueError('Ledger changes must agree with invoices and payments.')
        stocks={};movements={};transfers={};reversals={}
        for row in p['deltas']['stocks']:
            if row['location'] not in ('Warehouse','Outlet') or not math.isfinite(row['delta']):raise ValueError('Invalid stock delta.')
            key=(row['product_id'],row['location']);stocks[key]=stocks.get(key,0)+row['delta']
        for row in p['append'].get('movements',[]):
            loc=row['location'];q=row['quantity'];pid=row['product_id'];ref=row['reference']
            if loc not in ('Warehouse','Outlet') or not math.isfinite(q) or not q:raise ValueError('Invalid stock movement.')
            key=(pid,loc);movements[key]=movements.get(key,0)+q
            doc_id=ref[4:] if ref.startswith('REV-') else ref
            if doc_id in documents:
                doc=documents[doc_id]
                positive=(doc['kind']=='purchase')!=bool(doc['reversed'])
                if loc!=doc['location'] or (q>0)!=positive:raise ValueError('Invoice movement has the wrong direction or location.')
                if doc['reversed']:
                    key=(doc_id,pid,loc);reversals[key]=reversals.get(key,0)+q
            elif ref.startswith('TR-'):
                key=(ref,pid);transfers[key]=transfers.get(key,0)+q
            elif ref not in ('OPENING','ADJUST','DEMO'):raise ValueError('Unknown stock movement reference.')
        for key in stocks.keys()|movements.keys():
            if abs(stocks.get(key,0)-movements.get(key,0))>0.000001:raise ValueError('Stock balances must agree with movement history.')
        if any(abs(v)>0.000001 for v in transfers.values()):raise ValueError('Transfers must conserve total stock.')
        for (doc_id,pid,loc),q in reversals.items():
            original=db.execute('SELECT COALESCE(SUM(quantity),0) FROM movements WHERE reference=? AND product_id=? AND location=?',(doc_id,pid,loc)).fetchone()[0]
            if abs(q+original)>0.000001:raise ValueError('Reversal must restore original stock movements.')
        for row in p['append'].get('lines',[]):
            if row['document_id'] not in documents or documents[row['document_id']]['reversed']:raise ValueError('Lines must belong to a new invoice.')
        for row in p['append'].get('expenses',[]):
            if type(row['amount']) is not int or row['amount']<=0 or row['method'] not in ('Cash','UPI','Card','Bank'):raise ValueError('Invalid expense.')
    def exchange(self,token,data):
        if data.get('protocol')!=5:raise ValueError('Update Windows to 0.8.0 before syncing; saved records are preserved.')
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
                        db.execute('INSERT INTO sync_events VALUES(?,?,?,?)',(event['id'],event['date'],event['device'],json.dumps(event['payload'])))
                        self.shop.queue_synced_updates(db,event)
                        accepted.append(event['id'])
                except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:
                    errors.append({'id':event.get('id','invalid'),'message':str(e)[:200]})
                    break  # Preserve causal order: later invoices/payments wait behind the conflict.
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
    reply=request(url,'/api/device-pair',{'device_id':ident,'name':name,'code':str(data.get('code','')),'protocol':5})
    state=reply['snapshot']
    with shop.lock,shop.connect() as db:
        db.execute('DELETE FROM notifications')
        db.execute('DELETE FROM catalogue_products')
        db.execute('DELETE FROM catalogue_orders')
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
    return {'message':'PC paired. Server records loaded after a local backup. Every business function is available on this node.'}

def sync_desktop(shop):
    with shop.cloud_lock:
        return _sync_desktop(shop)

def _sync_desktop(shop):
    with shop.lock,shop.connect() as db:
        db.executescript(DDL);s=shop.settings(db);key=credential(shop)
        if not key.get('token'):raise ValueError('This PC has no connection credential. Review pairing before billing.')
        rows=db.execute('SELECT * FROM sync_events WHERE id NOT IN (SELECT event_id FROM cloud_sent) ORDER BY date,id LIMIT 50').fetchall()
        events=[{'version':1,'id':r['id'],'device':r['device'],'date':r['date'],'payload':json.loads(r['payload'])} for r in rows]
    reply=request(s['cloud_url'],'/api/device-sync',{'business_id':s['cloud_business_id'],'events':events,'cursor':s.get('cloud_cursor',0),'protocol':5},key['token'])
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

def change_server(shop,data):
    url=origin(data.get('url',''))
    with shop.cloud_lock,shop.lock:
        with shop.connect() as db:s=shop.settings(db);key=credential(shop)
        if not key.get('token') or not s.get('cloud_business_id'):raise ValueError('Pair this node first.')
        reply=request(url,'/api/device-sync',{'business_id':s['cloud_business_id'],'events':[],'cursor':s.get('cloud_cursor',0),'protocol':5},key['token'])
        if reply['business_id']!=s['cloud_business_id']:raise ValueError('This address belongs to another business.')
        with shop.connect() as db:
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(url),'cloud_url'))
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(''),'sync_folder'))
    return {'message':'Server address verified and updated. Existing records and pending transactions are preserved.'}

def disconnect(shop,data):
    if data.get('confirm')!='DISCONNECT':raise ValueError('Type DISCONNECT after all nodes have stopped billing and completed their final exchange.')
    with shop.cloud_lock:
        with shop.connect() as db:
            db.executescript(DDL)
            if not shop.settings(db).get('cloud_url'):raise ValueError('This PC is not connected to a server.')
        result=_sync_desktop(shop)
        if result['pending'] or result['more']:raise ValueError('Finish exchanging all pending records and resolve conflicts before disconnecting.')
        with shop.lock,shop.connect() as db:
            if db.execute('SELECT 1 FROM sync_errors').fetchone():raise ValueError('Resolve sync conflicts before disconnecting.')
            safety=shop.backup(local_only=True)
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(''),'cloud_url'))
            shop.audit(db,'server_disconnected',{'safety_backup':safety['paths'][0]})
    return {'message':'Final server exchange and backup completed. Billing remains offline. Configure the same shared folder on every reconciled node to continue exchange without a server.'}


def retire(shop,data):
    """Keep unsent records and recovery identity when the hub is permanently gone."""
    if data.get('confirm')!='RETIRED':raise ValueError('Type RETIRED only when the server has been permanently removed.')
    with shop.cloud_lock,shop.lock:
        with shop.connect() as db:
            db.executescript(DDL)
            if not shop.settings(db).get('cloud_url'):raise ValueError('This PC is not connected to a server.')
            pending=db.execute('SELECT COUNT(*) FROM sync_events WHERE id NOT IN (SELECT event_id FROM cloud_sent)').fetchone()[0]
            waiting=db.execute('SELECT COUNT(*) FROM cloud_inbox').fetchone()[0]
        safety=shop.backup(local_only=True)
        with shop.connect() as db:
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(''),'cloud_url'))
            # Folder sync and messaging stay off until the owner reconciles every node.
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(''),'sync_folder'))
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(False),'whatsapp_enabled'))
            shop.audit(db,'server_retired',{'safety_backup':safety['paths'][0],'pending':pending,'waiting':waiting})
    return {'pending':pending,'waiting':waiting,'message':f'Server connection removed after a local backup. {pending} unsent changes and {waiting} incoming changes are preserved. Reconcile all PCs and the saved server backup before setting up folder exchange.'}
