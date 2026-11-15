"""Lot (batch) stock: one product can hold several lots, each with its own expiry.

Lots are a breakdown of the stock held at a location. Stock that carries no lot
record stays valid as untracked stock, so every earlier flow keeps working.
Outgoing stock leaves the earliest-expiring lot first, and a sale never draws
from an expired lot.
"""
import datetime as dt,math

DDL='''CREATE TABLE IF NOT EXISTS lots(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),
  location TEXT NOT NULL,lot TEXT NOT NULL DEFAULT '',expiry TEXT NOT NULL DEFAULT '',quantity REAL NOT NULL DEFAULT 0,
  UNIQUE(product_id,location,lot,expiry));'''
NEAR_DAYS=30
EPSILON=0.000001

def today():
    from outreach import business_now
    return business_now({'whatsapp_timezone':'Asia/Kolkata'}).date().isoformat()

def clean(data):
    """Validated (lot number, expiry) from a form or a synced row."""
    lot=str(data.get('lot') or '').strip();expiry=str(data.get('expiry') or '').strip()
    if len(lot)>40:raise ValueError('A lot number has at most 40 characters.')
    if expiry and dt.date.fromisoformat(expiry).isoformat()!=expiry:raise ValueError('Enter the expiry date as YYYY-MM-DD.')
    return lot,expiry

def ensure(db):
    db.executescript(DDL)
    # The MRP printed on a pack can differ between lots of the same product.
    if 'mrp' not in {r[1] for r in db.execute('PRAGMA table_info(lots)')}:
        db.execute('ALTER TABLE lots ADD COLUMN mrp INTEGER NOT NULL DEFAULT 0')
    # Releases before 1.4.0 kept one expiry per product. Turn it into a lot over the stock on hand.
    for p in db.execute("SELECT id,expiry FROM products WHERE expiry<>''").fetchall():
        try:expiry=clean({'expiry':p['expiry']})[1]
        except ValueError:continue
        for s in db.execute('SELECT location,quantity FROM stocks WHERE product_id=?',(p['id'],)).fetchall():
            loose=s['quantity']-tracked(db,p['id'],s['location'])
            if loose>EPSILON:add(db,p['id'],s['location'],'',expiry,loose)
        db.execute("UPDATE products SET expiry='' WHERE id=?",(p['id'],))

def tracked(db,pid,location):
    return db.execute('SELECT COALESCE(SUM(quantity),0) FROM lots WHERE product_id=? AND location=?',(pid,location)).fetchone()[0]

def add(db,pid,location,lot,expiry,quantity,mrp=0):
    db.execute('INSERT OR IGNORE INTO lots(product_id,location,lot,expiry,quantity) VALUES(?,?,?,?,0)',(pid,location,lot,expiry))
    if mrp:db.execute('UPDATE lots SET mrp=? WHERE product_id=? AND location=? AND lot=? AND expiry=?',(int(mrp),pid,location,lot,expiry))
    db.execute('UPDATE lots SET quantity=MAX(0,ROUND(quantity+?,6)) WHERE product_id=? AND location=? AND lot=? AND expiry=?',(quantity,pid,location,lot,expiry))

def breakdown(db,product,location,stock):
    """Lots on hand, plus one untracked entry for stock that has no lot record."""
    rows=[{'lot':r['lot'],'expiry':r['expiry'],'quantity':r['quantity'],'mrp':r['mrp'],'tracked':True} for r in
          db.execute('SELECT lot,expiry,quantity,mrp FROM lots WHERE product_id=? AND location=? AND quantity>?',(product['id'],location,EPSILON))]
    loose=stock-sum(r['quantity'] for r in rows)
    if loose>EPSILON:rows.append({'lot':'','expiry':product['expiry'] or '','quantity':loose,'mrp':0,'tracked':False})
    return rows

def receive(db,pid,location,quantity,lot):
    """Record incoming stock against lots. `lot` is one {'lot','expiry'} or a list with quantities."""
    if not lot:return []
    parts=lot if isinstance(lot,list) else [{**lot,'quantity':quantity}]
    result=[];left=quantity
    for part in parts:
        name,expiry=clean(part);amount=min(float(part['quantity']),left);mrp=int(part.get('mrp') or 0)
        if mrp<0:raise ValueError('MRP cannot be negative.')
        if amount<=EPSILON or not (name or expiry or mrp):continue
        add(db,pid,location,name,expiry,amount,mrp);left-=amount
        result.append({'product_id':pid,'lot':name,'expiry':expiry,'quantity':round(amount,6),**({'mrp':mrp} if mrp else {})})
    return result

def take(db,product,location,quantity,stock,mode='any',lot=None,strict=False):
    """Remove outgoing stock from lots and return the tracked portions used.

    mode 'sale' uses only stock within expiry; 'any' prefers it; 'writeoff' takes
    the oldest dates first. `lot` names lots to draw from before the usual order.
    """
    day=today();rows=breakdown(db,product,location,stock);left=quantity;used=[]
    def expired(row):return bool(row['expiry']) and row['expiry']<day
    def draw(row,amount):
        nonlocal left
        amount=min(amount,row['quantity'],left)
        if amount<=EPSILON:return
        row['quantity']-=amount;left-=amount
        if row['tracked']:
            add(db,product['id'],location,row['lot'],row['expiry'],-amount)
            used.append({'product_id':product['id'],'lot':row['lot'],'expiry':row['expiry'],'quantity':round(amount,6),**({'mrp':row['mrp']} if row['mrp'] else {})})
    for wanted in ([] if not lot else lot if isinstance(lot,list) else [{**lot,'quantity':quantity}]):
        name,expiry=clean(wanted)
        row=next((r for r in rows if r['tracked'] and r['lot']==name and r['expiry']==expiry),None)
        amount=min(float(wanted['quantity']),left)
        if strict and (not row or row['quantity']+EPSILON<amount):
            raise ValueError(f"Lot {name or expiry or 'selected'} holds only {row['quantity'] if row else 0:g} {product['unit']} in {location}.")
        if row:draw(row,amount)
    dated=lambda r:(r['expiry']=='',r['expiry'])
    if mode=='writeoff':order=sorted(rows,key=dated)
    else:
        order=sorted((r for r in rows if not expired(r)),key=dated)
        if mode=='sale':
            valid=sum(r['quantity'] for r in order)
            if valid+EPSILON<left:
                raise ValueError(f"Only {valid:g} {product['unit']} of {product['name']} is within expiry in {location}. Write off or return the expired lot before selling more.")
        else:order+=sorted((r for r in rows if expired(r)),key=dated)
    for row in order:
        if left<=EPSILON:break
        draw(row,left)
    return used

def resolve(db,ident,pid,location):
    """The lot a form picked by row id, checked against the product and location."""
    row=db.execute('SELECT lot,expiry FROM lots WHERE id=? AND product_id=? AND location=?',(int(ident),pid,location)).fetchone()
    if not row:raise ValueError('That lot is no longer at this location. Refresh and choose again.')
    return {'lot':row['lot'],'expiry':row['expiry']}

def state(db):
    day=dt.date.fromisoformat(today());result=[]
    for r in db.execute('SELECT * FROM lots WHERE quantity>? ORDER BY expiry=\'\',expiry,lot',(EPSILON,)):
        row=dict(r);days=(dt.date.fromisoformat(r['expiry'])-day).days if r['expiry'] else None
        row['days']=days;row['status']='none' if days is None else 'expired' if days<0 else 'near' if days<=NEAR_DAYS else 'ok'
        result.append(row)
    return result

def deltas(before,after):
    """Lot quantity changes between two captures, for sync."""
    key=lambda r:(r['product_id'],r['location'],r['lot'],r['expiry'])
    old={key(r):r['quantity'] for r in before};result=[]
    for r in after:
        delta=round(r['quantity']-old.get(key(r),0),6)
        if delta:result.append({'product_id':r['product_id'],'location':r['location'],'lot':r['lot'],'expiry':r['expiry'],'delta':delta,**({'mrp':r['mrp']} if r.get('mrp') else {})})
    return result

def check(row):
    """Validate one synced lot change."""
    if set(row)-{'mrp'}!={'product_id','location','lot','expiry','delta'} or type(row.get('mrp',0)) is not int or row.get('mrp',0)<0 or row['location'] not in ('Warehouse','Outlet'):raise ValueError('Invalid synced lot.')
    if type(row['product_id']) is not int or not isinstance(row['delta'],(int,float)) or not math.isfinite(row['delta']):raise ValueError('Invalid synced lot quantity.')
    if not isinstance(row['lot'],str) or not isinstance(row['expiry'],str) or clean(row)!=(row['lot'],row['expiry']):raise ValueError('Invalid synced lot.')

def apply(db,rows):
    for row in rows:
        check(row)
        if not db.execute('SELECT 1 FROM products WHERE id=?',(row['product_id'],)).fetchone():raise ValueError('Lot refers to an unknown product.')
        add(db,row['product_id'],row['location'],row['lot'],row['expiry'],float(row['delta']),row.get('mrp',0))
