"""Partial returns: credit notes against sales and debit notes against purchases.

A note is its own numbered, immutable document that points at the original
invoice. Sale returns put goods back into the lots they left; purchase returns
take them out again. The unpaid part of the original is reduced first and the
rest is refunded.
"""
import json
from decimal import Decimal,ROUND_HALF_UP

KINDS={'sale':'sale_return','purchase':'purchase_return'}
MONEY=('total','tax','cost','taxable','gst_amount','cess_amount','cgst_amount','sgst_amount','igst_amount')

def returned(db,original_id):
    """Quantity already returned per line of the original document."""
    done={}
    for row in db.execute("SELECT snapshot FROM documents WHERE reference=? AND kind IN ('sale_return','purchase_return')",(original_id,)):
        for item in json.loads(row['snapshot'])['items']:done[item['line']]=done.get(item['line'],0)+item['quantity']
    return done

def create(shop,db,data):
    from app import now,number,money,required
    original=db.execute('SELECT * FROM documents WHERE id=?',(str(data.get('id','')),)).fetchone()
    if not original or original['kind'] not in KINDS:raise ValueError('Choose a saved bill or purchase to return against.')
    if original['reversed']:raise ValueError('This document was reversed in full. Nothing is left to return.')
    kind=KINDS[original['kind']];sale=kind=='sale_return'
    source=json.loads(original['snapshot']);settings=shop.settings(db);location=original['location']
    reason=required(data.get('reason'),'Reason');restock=bool(data.get('restock',True))
    already=returned(db,original['id']);wanted={}
    for entry in data.get('items',[]):
        line=int(entry['line']);quantity=number(entry['quantity'])
        if quantity>0:wanted[line]=wanted.get(line,0)+quantity
    if not wanted:raise ValueError('Enter a quantity for at least one item.')
    items=[];total=tax=0
    for line,quantity in sorted(wanted.items()):
        if not 0<=line<len(source['items']):raise ValueError('Item not found on the original document.')
        item=source['items'][line];left=item['quantity']-already.get(line,0)
        if quantity>left+0.000001:raise ValueError(f"Only {left:g} {item['unit']} of {item['name']} is left to return.")
        whole=abs(quantity-left)<0.000001 and not already.get(line)
        share=Decimal(str(quantity))/Decimal(str(item['quantity']))
        part={k:item[k] for k in ('product_id','name','sku','unit','hsn','price','gst','cess')}
        part.update(line=line,quantity=quantity)
        for key in MONEY:
            part[key]=item.get(key,0) if whole else int((Decimal(item.get(key,0))*share).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        # Keep the tax parts adding up after proportional rounding.
        part['taxable']=part['total']-part['tax'];part['gst_amount']=part['tax']-part['cess_amount']
        if part['igst_amount']:part['igst_amount']=part['gst_amount']
        else:part['cgst_amount']=part['gst_amount']//2;part['sgst_amount']=part['gst_amount']-part['cgst_amount']
        items.append(part);total+=part['total'];tax+=part['tax']
    party=dict(db.execute('SELECT * FROM parties WHERE id=?',(original['party_id'],)).fetchone() or {}) if original['party_id'] else {}
    # What is still owed on the original is cancelled first; only the rest is money back.
    outstanding=min(party.get('balance',0),original['total']-original['paid']) if party else 0
    credit=min(total,max(0,outstanding));refund=total-credit
    if 'refund' in data and data['refund'] not in ('',None):
        refund=money(data['refund'])
        if refund>total:raise ValueError('The refund cannot exceed the value returned.')
        credit=total-refund
        if credit>(party.get('balance',0) if party else 0):
            raise ValueError(f"Refund at least ₹{(total-(party.get('balance',0) if party else 0))/100:.2f}: only the amount still owed can be cancelled.")
    method=shop.method(data.get('payment','Cash')) if refund else 'Cash'
    ident='C' if sale else 'D'
    from outreach import business_now
    day=business_now({'whatsapp_timezone':'Asia/Kolkata'}).date();year=day.year if day.month>=4 else day.year-1
    prefix=f"{settings['invoice_prefix']}{settings['device_id'][:6].upper()}{ident}{str(year)[-2:]}"
    count=db.execute('SELECT COUNT(*) FROM documents WHERE id LIKE ?',(prefix+'%',)).fetchone()[0]+1
    if count>99999:raise ValueError('Note sequence is full. Start a new invoice prefix.')
    docid=prefix+str(count).zfill(5)
    pool={}
    for line in wanted:
        for part in source['items'][line].get('lots',[]):pool.setdefault(part['product_id'],[]).append(dict(part))
    for part in items:
        product=db.execute('SELECT kind FROM products WHERE id=?',(part['product_id'],)).fetchone()
        stocked=product and product['kind']!='recipe'
        if sale and not (restock and stocked):continue
        if not stocked:continue
        share,left=[],part['quantity']
        for lot in pool.get(part['product_id'],[]):
            amount=min(lot['quantity'],left)
            if amount>0.000001:share.append({**lot,'quantity':amount});lot['quantity']-=amount;left-=amount
        moved=shop.movement(db,part['product_id'],part['quantity'] if sale else -part['quantity'],docid,'Sale return' if sale else 'Purchase return',location,lot=share or None,take='writeoff')
        if moved:part['lots']=moved
    snapshot={'shop':source['shop'],'party':source.get('party',{}),'items':items,'location':location,'supply_state':source.get('supply_state',''),
              'tax_type':source.get('tax_type',''),'device_id':settings['device_id'],'original_id':original['id'],'original_date':original['date'],
              'reason':reason,'restocked':bool(sale and restock),'credit':credit}
    if refund:snapshot['payments']=[{'method':method,'amount':refund}]
    db.execute('INSERT INTO documents(id,kind,date,party_id,total,tax,paid,payment,discount,reference,snapshot,location) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
               (docid,kind,now(),original['party_id'],total,tax,refund,method,0,original['id'],json.dumps(snapshot),location))
    if credit:db.execute('UPDATE parties SET balance=balance-? WHERE id=?',(credit,original['party_id']))
    return {'id':docid,'refund':refund,'credit':credit,'method':method}
