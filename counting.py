"""Stock count: enter what is physically on the shelf and post the differences in one step."""

def apply(shop,db,data):
    from app import number
    location=shop.location(data.get('location','Warehouse'));note=str(data.get('note') or '').strip()[:120]
    rows=data.get('counts') or []
    if not rows or len(rows)>2000:raise ValueError('Enter between 1 and 2,000 counted products.')
    seen=set();variance=[]
    for row in rows:
        pid=int(row['product_id']);counted=number(row['counted'])
        if pid in seen:raise ValueError('A product appears twice in this count.')
        seen.add(pid)
        product=db.execute('SELECT name,unit,kind FROM products WHERE id=?',(pid,)).fetchone()
        if not product or product['kind']=='recipe':raise ValueError('Count stocked products and ingredients only.')
        held=db.execute('SELECT quantity FROM stocks WHERE product_id=? AND location=?',(pid,location)).fetchone()
        difference=round(counted-(held[0] if held else 0),6)
        if not difference:continue
        # A shortage clears the oldest dates first, the same as wastage.
        shop.movement(db,pid,difference,'ADJUST','Stock count'+(': '+note if note else ''),location,take='writeoff')
        variance.append({'product_id':pid,'name':product['name'],'unit':product['unit'],'difference':difference})
    return {'counted':len(rows),'adjusted':len(variance),'variance':variance}
