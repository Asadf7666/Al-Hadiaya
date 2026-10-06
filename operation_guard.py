"""Persist retry keys in the same SQLite transaction as stock and ledger writes."""
import hashlib,json,re
ACTIONS={'sale','purchase','payment','expense','transfer','adjust','reverse','party','product','import_products','recipe','inventory_plan','purchase_order_create','purchase_order_status','trade_order_status','trade_order_reprice'}
def migrate(db):db.execute('CREATE TABLE IF NOT EXISTS operation_requests(id TEXT PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,digest TEXT NOT NULL,response TEXT NOT NULL)')
def fingerprint(action,data):
 clean={k:v for k,v in data.items() if not k.startswith('_request_')}
 return hashlib.sha256(json.dumps(clean,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def begin(db,action,data):
 if action not in ACTIONS or not data.get('_request_id'):return None
 ident=data['_request_id'];actor=data.get('_request_actor','local')
 if not re.fullmatch(r'[0-9a-f]{32}',ident) or len(actor)>100:raise ValueError('Invalid operation retry key.')
 db.execute('BEGIN IMMEDIATE')
 row=db.execute('SELECT * FROM operation_requests WHERE id=?',(ident,)).fetchone()
 if row:
  if row['actor']!=actor or row['action']!=action or row['digest']!=fingerprint(action,data):raise ValueError('This retry key belongs to another operation. Refresh and review before saving.')
  return json.loads(row['response'])
 return None
def finish(db,action,data,result):
 if action in ACTIONS and data.get('_request_id'):db.execute('INSERT INTO operation_requests VALUES(?,?,?,?,?)',(data['_request_id'],data.get('_request_actor','local'),action,fingerprint(action,data),json.dumps(result)))
