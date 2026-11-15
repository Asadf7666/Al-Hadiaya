"""Change tracking for sync: what one action changed, without copying whole tables.

Database triggers note each touched row and keep its earlier value in a shadow
table. Building a sync event then costs in proportion to what the action
changed, not to how much history the shop holds. `begin` empties the shadows,
the action runs, and `payload` reads them back into the same event layout the
older table-comparison produced.
"""
import hashlib

MASTERS=('products','parties','documents','devices','commerce_products','trade_orders','inventory_plans','purchase_orders')
EXCLUDED={'products':'stock','parties':'balance'}
APPENDED=('lines','movements','payments','expenses')
# Quantity tables: key columns, and the row identity used to pair old with new.
AMOUNTS={'stocks':('product_id','location'),'allocations':('device_id','product_id','location'),'lots':('id',)}
SETTINGS=('name','address','phone','gstin','state','gst_enabled','invoice_prefix','demo','admin_device_id','node_mode','fssai','composition','upi_id','round_off')
SHADOWS=tuple('_was_'+t for t in MASTERS+tuple(AMOUNTS)+('recipes','settings'))+('_new_rows','_recipes_touched')

def _columns(db,table):return [r[1] for r in db.execute('PRAGMA table_info('+table+')')]
def _exists(db,table):return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())

def _signature(db):
    parts=['v3']+[t+':'+','.join(_columns(db,t)) for t in MASTERS+tuple(AMOUNTS)+APPENDED+('recipes','settings')]
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()

def install(db):
    """Create or refresh the shadow tables and triggers. Safe to call at any time."""
    signature=_signature(db)
    if _exists(db,'_track_meta') and (db.execute('SELECT signature FROM _track_meta').fetchone() or [''])[0]==signature:return
    for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'track!_%' ESCAPE '!'").fetchall():db.execute('DROP TRIGGER '+row[0])
    for name in SHADOWS:db.execute('DROP TABLE IF EXISTS '+name)
    db.execute('CREATE TABLE IF NOT EXISTS _track_meta(signature TEXT)');db.execute('DELETE FROM _track_meta')
    db.execute('CREATE TABLE _new_rows(tbl TEXT NOT NULL,id INTEGER NOT NULL,PRIMARY KEY(tbl,id))')
    for table in MASTERS:
        if not _exists(db,table):continue
        cols=_columns(db,table);listed=','.join(cols);shadow='_was_'+table
        db.execute(f'CREATE TABLE {shadow}(_new INTEGER NOT NULL DEFAULT 0,{listed},UNIQUE(id))')
        # The statement that fires a trigger overrides a conflict clause inside it, so each step guards itself.
        copy=lambda ref:f'INSERT INTO {shadow}(_new,{listed}) SELECT 0,{listed} FROM {table} WHERE id={ref}.id AND NOT EXISTS(SELECT 1 FROM {shadow} WHERE id={ref}.id);'
        db.execute(f'CREATE TRIGGER track_{table}_u BEFORE UPDATE ON {table} BEGIN {copy("OLD")} END')
        db.execute(f'CREATE TRIGGER track_{table}_b BEFORE INSERT ON {table} BEGIN {copy("NEW")} END')
        db.execute(f'CREATE TRIGGER track_{table}_i AFTER INSERT ON {table} BEGIN INSERT INTO {shadow}(_new,id) SELECT 1,NEW.id WHERE NOT EXISTS(SELECT 1 FROM {shadow} WHERE id=NEW.id); END')
    for table,key in AMOUNTS.items():
        shadow='_was_'+table;listed=','.join(key)
        db.execute(f'CREATE TABLE {shadow}({listed},quantity,UNIQUE({listed}))')
        old=' AND '.join(f'{k}=OLD.{k}' for k in key);new=' AND '.join(f'{k}=NEW.{k}' for k in key)
        seen=lambda ref:'NOT EXISTS(SELECT 1 FROM '+shadow+' WHERE '+' AND '.join(f'{k}={ref}.{k}' for k in key)+')'
        db.execute(f'CREATE TRIGGER track_{table}_u BEFORE UPDATE ON {table} BEGIN INSERT INTO {shadow}({listed},quantity) SELECT {listed},quantity FROM {table} WHERE {old} AND {seen("OLD")}; END')
        db.execute(f'CREATE TRIGGER track_{table}_b BEFORE INSERT ON {table} BEGIN INSERT INTO {shadow}({listed},quantity) SELECT {listed},quantity FROM {table} WHERE {new} AND {seen("NEW")}; END')
        db.execute(f"CREATE TRIGGER track_{table}_i AFTER INSERT ON {table} BEGIN INSERT INTO {shadow}({listed},quantity) SELECT {','.join('NEW.'+k for k in key)},0 WHERE {seen('NEW')}; END")
    for table in APPENDED:
        db.execute(f"CREATE TRIGGER track_{table}_i AFTER INSERT ON {table} BEGIN INSERT INTO _new_rows SELECT '{table}',NEW.id WHERE NOT EXISTS(SELECT 1 FROM _new_rows WHERE tbl='{table}' AND id=NEW.id); END")
    db.execute('CREATE TABLE _was_recipes(rid INTEGER,product_id,ingredient_id,quantity)');db.execute('CREATE TABLE _recipes_touched(product_id PRIMARY KEY)')
    keep=lambda ref:(f'INSERT INTO _was_recipes SELECT rowid,product_id,ingredient_id,quantity FROM recipes WHERE product_id={ref}.product_id '
                     f'AND NOT EXISTS(SELECT 1 FROM _recipes_touched WHERE product_id={ref}.product_id); INSERT INTO _recipes_touched SELECT {ref}.product_id WHERE NOT EXISTS(SELECT 1 FROM _recipes_touched WHERE product_id={ref}.product_id);')
    db.execute(f'CREATE TRIGGER track_recipes_i BEFORE INSERT ON recipes BEGIN {keep("NEW")} END')
    db.execute(f'CREATE TRIGGER track_recipes_d BEFORE DELETE ON recipes BEGIN {keep("OLD")} END')
    db.execute(f'CREATE TRIGGER track_recipes_u BEFORE UPDATE ON recipes BEGIN {keep("OLD")} {keep("NEW")} END')
    db.execute('CREATE TABLE _was_settings(key PRIMARY KEY,value,_new INTEGER NOT NULL DEFAULT 0)')
    db.execute('CREATE TRIGGER track_settings_u BEFORE UPDATE ON settings BEGIN INSERT INTO _was_settings(key,value) SELECT OLD.key,OLD.value WHERE NOT EXISTS(SELECT 1 FROM _was_settings WHERE key=OLD.key); END')
    db.execute('CREATE TRIGGER track_settings_b BEFORE INSERT ON settings BEGIN INSERT INTO _was_settings(key,value) SELECT key,value FROM settings WHERE key=NEW.key AND NOT EXISTS(SELECT 1 FROM _was_settings WHERE key=NEW.key); END')
    db.execute('CREATE TRIGGER track_settings_i AFTER INSERT ON settings BEGIN INSERT INTO _was_settings(key,value,_new) SELECT NEW.key,NULL,1 WHERE NOT EXISTS(SELECT 1 FROM _was_settings WHERE key=NEW.key); END')
    db.execute('INSERT INTO _track_meta VALUES(?)',(signature,))

def begin(db):
    """Start tracking one action: make sure the triggers match the schema, then forget earlier changes."""
    install(db)
    for name in SHADOWS:
        if _exists(db,name):db.execute('DELETE FROM '+name)

def payload(db):
    """The sync event for everything changed since `begin`."""
    result={'masters':{},'append':{},'deltas':{'stocks':[],'parties':[],'allocations':[],'lots':[]},'settings':[],'recipes':[]}
    for table in MASTERS:
        changed=[]
        if _exists(db,'_was_'+table):
            was={r['id']:dict(r) for r in db.execute(f'SELECT * FROM _was_{table}')}
            excluded=EXCLUDED.get(table)
            for row in db.execute(f'SELECT * FROM {table} WHERE id IN (SELECT id FROM _was_{table}) ORDER BY rowid') if was else []:
                current=dict(row);old=was[row['id']];fresh=old.pop('_new')
                previous={} if fresh else {k:old.get(k) for k in current}
                if table=='parties':
                    delta=row['balance']-(0 if fresh else old['balance'])
                    if delta:result['deltas']['parties'].append({'id':row['id'],'delta':delta})
                if excluded:
                    current.pop(excluded);previous.pop(excluded,None)
                if previous!=current:changed.append(current)
        result['masters'][table]=changed
    for table in ('stocks','allocations'):
        key=AMOUNTS[table];join=' AND '.join(f't.{k}=w.{k}' for k in key)
        for row in db.execute(f'SELECT t.*,w.quantity AS _was FROM {table} t JOIN _was_{table} w ON {join} ORDER BY t.rowid'):
            delta=row['quantity']-row['_was']
            if delta:result['deltas'][table].append({**{k:row[k] for k in key},'delta':delta})
    for row in db.execute('SELECT t.*,w.quantity AS _was FROM lots t JOIN _was_lots w ON t.id=w.id ORDER BY t.id'):
        delta=round(row['quantity']-row['_was'],6)
        if delta:result['deltas']['lots'].append({'product_id':row['product_id'],'location':row['location'],'lot':row['lot'],'expiry':row['expiry'],'delta':delta,**({'mrp':row['mrp']} if row['mrp'] else {})})
    for table in APPENDED:
        result['append'][table]=[{k:v for k,v in dict(r).items() if k!='id'} for r in db.execute(f"SELECT * FROM {table} WHERE id IN (SELECT id FROM _new_rows WHERE tbl=?) ORDER BY id",(table,))]
    for touched in db.execute('SELECT product_id FROM _recipes_touched').fetchall():
        pid=touched[0]
        previous=[dict(r) for r in db.execute('SELECT product_id,ingredient_id,quantity FROM _was_recipes WHERE product_id=? ORDER BY rid',(pid,))]
        current=[dict(r) for r in db.execute('SELECT * FROM recipes WHERE product_id=? ORDER BY rowid',(pid,))]
        if previous!=current:result['recipes'].append({'product_id':pid,'items':current})
    result['settings']=[{'key':r['key'],'value':r['value']} for r in db.execute('SELECT s.key,s.value,w.value AS _was,w._new FROM settings s JOIN _was_settings w ON w.key=s.key ORDER BY s.rowid')
                        if r['key'] in SETTINGS and (r['_new'] or r['value']!=r['_was'])]
    return result
