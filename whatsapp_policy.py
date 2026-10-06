"""Business-specific controls grounded in Meta policies reviewed 2026-10-06.

These controls reduce risk; they do not predict or override Meta enforcement.
"""
import datetime as dt,hashlib,json,re,time,urllib.request,urllib.error

FOOD_CATEGORIES={'cold drinks','water','packaged water','juices','energy drinks','ice cream','snacks','coffee','tea & coffee','tea','mojitos','dairy & milk','dairy & milk products','ingredients'}
RESTRICTED=re.compile(r'\b(alcohol|alcoholic|beer|wine|vodka|whisky|whiskey|rum|gin|tobacco|cigarettes?|vapes?|e-cigarettes?|cannabis|cbd|guns?|ammunition|explosives?|gambling|lottery|prescription|supplements?|steroids?)\b',re.I)
SENSITIVE=re.compile(r'(?i)(?:card number|bank account|account number|aadhaar|aadhar|passport|otp|one.time password)\s*[:=]?\s*[\d -]{6,}|(?:access token|app secret|password)\s*[:=]\s*\S{6,}')

def migrate(db):
 db.executescript('''CREATE TABLE IF NOT EXISTS whatsapp_sender_check(identity TEXT PRIMARY KEY,checked REAL,review TEXT,quality TEXT);
 CREATE TABLE IF NOT EXISTS whatsapp_send_throttle(phone TEXT PRIMARY KEY,attempted REAL);
 CREATE TABLE IF NOT EXISTS whatsapp_marketing_history(phone TEXT PRIMARY KEY,sent REAL);
 CREATE TABLE IF NOT EXISTS catalogue_policy_reviews(product_id INTEGER PRIMARY KEY,digest TEXT NOT NULL,reviewed TEXT NOT NULL);''')

def identity(s,token):return hashlib.sha256(json.dumps([s.get('whatsapp_waba_id'),s.get('whatsapp_phone_id'),s.get('whatsapp_api_version'),token]).encode()).hexdigest()

def sender_ready(shop,s,token):
 if not re.fullmatch(r'\d+',s.get('whatsapp_waba_id','')):return False,'Configure a WhatsApp Business Account ID before sending.'
 key=identity(s,token);stamp=time.time()
 with shop.connect() as db:cached=db.execute('SELECT * FROM whatsapp_sender_check WHERE identity=?',(key,)).fetchone()
 if not cached or stamp-cached['checked']>=600:
  review='UNAVAILABLE';quality='UNKNOWN'
  try:
   values=[]
   for path in [s['whatsapp_waba_id']+'?fields=account_review_status',s['whatsapp_waba_id']+'/phone_numbers?fields=id,quality_rating&limit=100']:
    request=urllib.request.Request('https://graph.facebook.com/'+s['whatsapp_api_version']+'/'+path,headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(request,timeout=10) as response:values.append(json.load(response))
   review=str(values[0].get('account_review_status','UNKNOWN'));number=next((r for r in values[1].get('data',[]) if str(r.get('id'))==s['whatsapp_phone_id']),{});quality=str(number.get('quality_rating','UNKNOWN'))
  except (urllib.error.URLError,TimeoutError,OSError,ValueError):pass
  with shop.lock,shop.connect() as db:db.execute('INSERT OR REPLACE INTO whatsapp_sender_check VALUES(?,?,?,?)',(key,stamp,review,quality))
 else:review,quality=cached['review'],cached['quality']
 if review!='APPROVED' or quality not in ('GREEN','YELLOW'):
  reason='Sender validation blocked sending: account review '+review+', number quality '+quality+'. Check Meta before retrying.'
  with shop.lock,shop.connect() as db:
   db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('whatsapp_pause_reason',json.dumps(reason)))
   if review=='REJECTED' or quality=='RED':db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(False),'whatsapp_enabled'))
  return False,reason
 if not s.get('phone') and not s.get('address'):
  reason='Add the shop support phone or address in Business settings before enabling automated replies.'
  with shop.connect() as db:db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('whatsapp_pause_reason',json.dumps(reason)))
  return False,reason
 with shop.connect() as db:db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(''),'whatsapp_pause_reason'))
 return True,''

def product_allowed(p,description=''):
 if str(p['category']).strip().lower() not in FOOD_CATEGORIES:raise ValueError('This catalogue supports the shop’s food and non-alcoholic drink categories. Review other categories separately.')
 if RESTRICTED.search(' '.join(str(p[k]) for k in ('name','category','brand'))+' '+description):raise ValueError('Restricted or regulated product wording needs review. This app does not support regulated goods in its WhatsApp catalogue.')
 if p['kind']=='ingredient':raise ValueError('Ingredients are managed internally; publish prepared or packaged sale products.')

def catalogue_digest(p,asset,description):return hashlib.sha256(json.dumps([p[k] for k in ('name','category','brand','kind','price')]+[asset,description]).encode()).hexdigest()
def approve_catalogue(db,p,asset,description,confirmed):
 product_allowed(p,description)
 if confirmed not in (True,'on'):raise ValueError('Confirm that this is a genuine permitted item, with an accurate photo, price and description.')
 db.execute('INSERT OR REPLACE INTO catalogue_policy_reviews VALUES(?,?,?)',(p['id'],catalogue_digest(p,asset,description),dt.datetime.now(dt.timezone.utc).isoformat()))
def catalogue_ready(db,p,asset,description):
 try:product_allowed(p,description)
 except ValueError:return False
 row=db.execute('SELECT digest FROM catalogue_policy_reviews WHERE product_id=?',(p['id'],)).fetchone()
 return bool(row and row['digest']==catalogue_digest(p,asset,description))

def message_allowed(row):
 values=json.loads(row.get('parameters','[]'))
 if row.get('message_type')=='session':values.append(json.loads(row.get('payload','{}')).get('text',{}).get('body',''))
 if SENSITIVE.search('\n'.join(map(str,values))):raise ValueError('Sensitive identifiers or credentials must not be sent through WhatsApp.')
