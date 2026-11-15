"""Verification aid: the older whole-table comparison, used to check change tracking.

Not used in normal running. With AL_HIDAYA_VERIFY_CAPTURE=1 every sync event is
built both ways and any difference raises.
"""
import json

def snapshot(db):
    return {t:[dict(r) for r in db.execute('SELECT * FROM '+t)] for t in
            ('products','parties','recipes','stocks','documents','lines','movements','payments','expenses','settings','devices','allocations','commerce_products','trade_orders','inventory_plans','purchase_orders','lots')}


def reference(db,before):
    after = snapshot(db)
    payload = {'masters':{},'append':{},'deltas':{'stocks':[],'parties':[],'allocations':[],'lots':__import__('lots').deltas(before['lots'],after['lots'])},'settings':[],'recipes':[]}
    for table in ('products','parties','documents','devices','commerce_products','trade_orders','inventory_plans','purchase_orders'):
        old = {r['id']:r for r in before[table]}
        changed = []
        for r in after[table]:
            row = dict(r)
            excluded = 'stock' if table == 'products' else 'balance' if table == 'parties' else None
            if excluded:
                row.pop(excluded)
            prev = dict(old.get(r['id'],{}))
            if excluded:
                prev.pop(excluded,None)
            if prev != row:
                changed.append(row)
            if table == 'parties':
                delta = r['balance']-old.get(r['id'],{}).get('balance',0)
                if delta:
                    payload['deltas']['parties'].append({'id':r['id'],'delta':delta})
        payload['masters'][table] = changed
    oldstock = {(r['product_id'],r['location']):r['quantity'] for r in before['stocks']}
    for r in after['stocks']:
        delta = r['quantity']-oldstock.get((r['product_id'],r['location']),0)
        if delta:
            payload['deltas']['stocks'].append({'product_id':r['product_id'],'location':r['location'],'delta':delta})
    oldallocations = {(r['device_id'],r['product_id'],r['location']):r['quantity'] for r in before['allocations']}
    for r in after['allocations']:
        delta = r['quantity']-oldallocations.get((r['device_id'],r['product_id'],r['location']),0)
        if delta:
            payload['deltas']['allocations'].append({'device_id':r['device_id'],'product_id':r['product_id'],'location':r['location'],'delta':delta})
    for table in ('lines','movements','payments','expenses'):
        oldids = {r['id'] for r in before[table]}
        payload['append'][table] = [{k:v for k,v in r.items() if k != 'id'} for r in after[table] if r['id'] not in oldids]
    for pid in {r['product_id'] for r in before['recipes']+after['recipes']}:
        previous = [r for r in before['recipes'] if r['product_id'] == pid]
        current = [r for r in after['recipes'] if r['product_id'] == pid]
        if previous != current:
            payload['recipes'].append({'product_id':pid,'items':current})
    allowed = ('name','address','phone','gstin','state','gst_enabled','invoice_prefix','demo','admin_device_id','node_mode','fssai','composition','upi_id','round_off')
    prevsettings = {r['key']:r['value'] for r in before['settings']}
    payload['settings'] = [r for r in after['settings'] if r['key'] in allowed and r['value'] != prevsettings.get(r['key'])]
    return payload

def _normal(payload):
    copy=json.loads(json.dumps(payload))
    copy['recipes']=sorted(copy['recipes'],key=lambda r:r['product_id'])
    return copy

def compare(db,before,tracked):
    expected=reference(db,before)
    if _normal(expected)!=_normal(tracked):
        for key in ('masters','append','deltas'):
            for name in set(expected[key])|set(tracked[key]):
                if _normal({'recipes':[],'x':expected[key].get(name)})!=_normal({'recipes':[],'x':tracked[key].get(name)}):
                    raise AssertionError(f'Change tracking differs in {key}.{name}: expected {expected[key].get(name)!r} got {tracked[key].get(name)!r}')
        raise AssertionError(f'Change tracking differs: expected {expected!r} got {tracked!r}')
