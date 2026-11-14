"""Cashier shifts and day close for this PC's cash drawer.

A shift starts with an opening float. Closing it compares the cash counted in
the drawer with what the recorded transactions say should be there, and keeps
the summary as the day-end report. Shifts belong to one PC and are not synced.
"""
import json

DDL='''CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY,opened TEXT NOT NULL,opened_by TEXT NOT NULL DEFAULT '',opening_float INTEGER NOT NULL DEFAULT 0,
  closed TEXT NOT NULL DEFAULT '',closed_by TEXT NOT NULL DEFAULT '',counted INTEGER NOT NULL DEFAULT 0,expected INTEGER NOT NULL DEFAULT 0,note TEXT NOT NULL DEFAULT '',summary TEXT NOT NULL DEFAULT '{}');'''
METHODS=('Cash','UPI','Card','Bank')

def ensure(db):db.executescript(DDL)

def _who(db,data):
    actor=str(data.get('_request_actor') or '').split(':')[0]
    if actor.isdigit() and db.execute("SELECT 1 FROM sqlite_master WHERE name='web_users'").fetchone():
        row=db.execute('SELECT name FROM web_users WHERE id=?',(int(actor),)).fetchone()
        if row:return row['name']
    return 'Owner'

def summary(db,shift,device,until=''):
    """Money in and out by payment method since the shift opened."""
    money={m:{'in':0,'out':0} for m in METHODS}
    counts={'sales':0,'sales_total':0,'returns':0,'returns_total':0,'purchases':0,'purchases_total':0,'credit_given':0,'expenses':0,'collections':0,'supplier_payments':0}
    window=' AND date>=?'+(' AND date<=?' if until else '');args=(shift['opened'],)+((until,) if until else ())
    for doc in db.execute('SELECT * FROM documents WHERE reversed=0'+window,args):
        snapshot=json.loads(doc['snapshot'])
        if snapshot.get('device_id')!=device:continue
        incoming=doc['kind'] in ('sale','purchase_return')
        for tender in snapshot.get('payments') or ([{'method':doc['payment'],'amount':doc['paid']}] if doc['paid'] else []):
            if tender['method'] in money:money[tender['method']]['in' if incoming else 'out']+=tender['amount']
        if doc['kind']=='sale':counts['sales']+=1;counts['sales_total']+=doc['total'];counts['credit_given']+=doc['total']-doc['paid']
        elif doc['kind']=='sale_return':counts['returns']+=1;counts['returns_total']+=doc['total']
        elif doc['kind']=='purchase':counts['purchases']+=1;counts['purchases_total']+=doc['total']
    for pay in db.execute('SELECT p.amount,p.method,t.kind FROM payments p JOIN parties t ON t.id=p.party_id WHERE 1=1'+window.replace('date','p.date'),args):
        customer=pay['kind']=='customer'
        if pay['method'] in money:money[pay['method']]['in' if customer else 'out']+=pay['amount']
        counts['collections' if customer else 'supplier_payments']+=pay['amount']
    for expense in db.execute('SELECT amount,method FROM expenses WHERE 1=1'+window,args):
        if expense['method'] in money:money[expense['method']]['out']+=expense['amount']
        counts['expenses']+=expense['amount']
    expected=shift['opening_float']+money['Cash']['in']-money['Cash']['out']
    return {**counts,'methods':money,'opening_float':shift['opening_float'],'expected_cash':expected}

def act(shop,action,data):
    from app import now,money
    with shop.lock,shop.connect() as db:
        current=db.execute("SELECT * FROM shifts WHERE closed='' ORDER BY id DESC").fetchone()
        device=shop.settings(db)['device_id']
        if action=='shift_open':
            if current:raise ValueError('A shift is already open on this PC. Close it first.')
            db.execute('INSERT INTO shifts(opened,opened_by,opening_float) VALUES(?,?,?)',(now(),_who(db,data),money(data.get('opening_float',0))))
            shop.audit(db,'shift_open',{'opening_float':data.get('opening_float',0)})
            return {'ok':True}
        if not current:raise ValueError('No shift is open on this PC.')
        closed=now();report=summary(db,current,device,closed);counted=money(data.get('counted',0))
        report.update(counted_cash=counted,difference=counted-report['expected_cash'])
        db.execute('UPDATE shifts SET closed=?,closed_by=?,counted=?,expected=?,note=?,summary=? WHERE id=?',
                   (closed,_who(db,data),counted,report['expected_cash'],str(data.get('note') or '')[:200],json.dumps(report),current['id']))
        shop.audit(db,'shift_close',{'id':current['id'],'difference':report['difference']})
        return {'id':current['id'],**report}

def state(db,device):
    current=db.execute("SELECT * FROM shifts WHERE closed='' ORDER BY id DESC").fetchone()
    recent=[{**dict(r),'summary':json.loads(r['summary'])} for r in db.execute("SELECT * FROM shifts WHERE closed<>'' ORDER BY id DESC LIMIT 30")]
    return {'shift':{**dict(current),'summary':summary(db,current,device)} if current else None,'shifts':recent}
