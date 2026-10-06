"""Sustained keyboard POS/purchase acceptance with a 10,000-SKU isolated fixture."""
import argparse,json,statistics,sys,tempfile,threading,time
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Shop
from desktop_http import DesktopHandler
from staff_access import StaffAccess
from playwright.sync_api import sync_playwright
from tools.browser_keyboard_check import focused

def seed(shop):
 supplier=shop.act('party',{'name':'Load Supplier','kind':'supplier'})['id']
 customer=shop.act('party',{'name':'Load Customer','kind':'customer'})['id']
 pid=shop.act('product',dict(name='TEST ONLY Load Drink',sku='LOAD',category='Cold drinks',unit='bottle',kind='stock',price=50,cost=20,stock=1000,pack=24,location='Warehouse'))['id']
 with shop.connect() as db:
  template=dict(db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone());profile=dict(db.execute('SELECT * FROM parties WHERE id=?',(customer,)).fetchone());db.execute('DELETE FROM movements');db.execute('DELETE FROM stocks');db.execute('DELETE FROM products');db.execute('DELETE FROM parties WHERE id=?',(customer,));keys=list(template)
  rows=[{**template,'id':10000+i,'name':f'TEST ONLY Load Drink {i:05d}','sku':f'LOAD-{i:05d}','barcode':str(8909000000000+i)} for i in range(10000)]
  db.executemany('INSERT INTO products('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',[[r[k] for k in keys] for r in rows]);db.executemany('INSERT INTO stocks VALUES(?,?,?)',[(r['id'],'Warehouse',1000) for r in rows])
  keys=list(profile);rows=[{**profile,'id':50000+i,'name':f'TEST ONLY Customer {i:03d}','phone':str(9800000000+i)} for i in range(300)]
  db.executemany('INSERT INTO parties('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',[[r[k] for k in keys] for r in rows])
 return supplier

def type_current(page,text):page.keyboard.press('Control+A');page.keyboard.insert_text(text)
def main(report=None):
 with tempfile.TemporaryDirectory() as folder:
  shop=Shop(folder);supplier=seed(shop);DesktopHandler.shop=shop;server=ThreadingHTTPServer(('127.0.0.1',0),DesktopHandler);server.access=StaffAccess(folder,'http://localhost',False,local=True,shop=shop);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1400,'height':950});errors=[];page.on('pageerror',lambda e:errors.append(e.stack));page.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:') else r.abort())
    page.goto('http://127.0.0.1:'+str(server.server_port));focused(page,'#login-username');page.keyboard.insert_text('owner');page.keyboard.press('Tab');page.keyboard.insert_text('load-check-password');page.keyboard.press('Enter');page.wait_for_function("typeof S!=='undefined'&&!!S&&!!document.querySelector('#keyboard-help')")
    timings=page.evaluate("""()=>{const t=performance.now();navTo('billing');const opening=performance.now()-t,times=[];for(let i=0;i<5;i++){const start=performance.now();addCart(10000);times.push(performance.now()-start);}clearCart();return {catalogue: S.products.length,opening_ms:opening,add_ms:times};}""")
    assert page.locator('.product-card').count()<=60
    page.keyboard.press('F3');focused(page,'#product-search');page.keyboard.press('PageDown');focused(page,'.product-card');assert page.evaluate('posOffset')==60;page.keyboard.press('PageUp');page.keyboard.press('F3')
    page.evaluate("window.scanField=document.querySelector('#product-search');window.mainNode=document.querySelector('#main');window.scanTimes=[];document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.id==='product-search'&&e.target.value){const t=performance.now();requestAnimationFrame(()=>scanTimes.push(performance.now()-t));}},true)")
    started=time.monotonic()
    for i in range(100):
     code=str(8909000000000+[0,1578,9999][i%3]);page.keyboard.type(code);page.keyboard.press('Enter');focused(page,'#product-search');assert page.locator('#product-search').input_value()==''
    assert page.evaluate('cart.reduce((n,l)=>n+l.quantity,0)')==100
    assert page.evaluate("scanField===document.querySelector('#product-search')&&mainNode===document.querySelector('#main')")
    timings['100_scans_wall_ms']=round((time.monotonic()-started)*1000,2);timings['scan_to_frame_ms']=page.evaluate('scanTimes.slice(0,100)')
    # A held Enter adds once; unknown or ambiguous codes add nothing.
    page.keyboard.type('8909000000000');page.keyboard.down('Enter');page.keyboard.down('Enter');page.keyboard.up('Enter');assert page.evaluate('cart.reduce((n,l)=>n+l.quantity,0)')==101
    page.keyboard.type('9999999999999');page.keyboard.press('Enter');assert page.evaluate('cart.reduce((n,l)=>n+l.quantity,0)')==101;type_current(page,'')
    page.evaluate("window.catalogueBeforeAmbiguity=S;S={...S,products:[...S.products,{...S.products.find(p=>p.id===10001),barcode:'8909000000000'}]};");page.keyboard.type('8909000000000');page.keyboard.press('Enter');assert page.evaluate('cart.reduce((n,l)=>n+l.quantity,0)')==101;page.evaluate('S=catalogueBeforeAmbiguity');type_current(page,'')
    page.keyboard.type('8909000000001');page.keyboard.press('Enter');page.keyboard.press('F6');focused(page,'[data-cart-quantity]');type_current(page,'0');page.keyboard.press('Enter');focused(page,'#product-search');assert page.evaluate('cart.reduce((n,l)=>n+l.quantity,0)')==101
    page.keyboard.type('8909000000000');page.keyboard.press('Enter');page.keyboard.press('F6');focused(page,'[data-cart-quantity]');type_current(page,'35');page.keyboard.press('Enter');page.keyboard.press('F6');focused(page,'[data-cart-quantity]');type_current(page,'1001');page.keyboard.press('Enter');focused(page,'[data-cart-quantity]');assert page.locator(':focus').input_value()=='35'
    type_current(page,'12');page.keyboard.press('Enter');focused(page,'#product-search');page.keyboard.press('F6');page.keyboard.press('Control+ArrowDown');focused(page,'[data-cart-quantity]')
    # Customer search and discount have direct shortcuts; saves never use bare Enter.
    page.keyboard.press('F5');focused(page,'#customer-query');page.keyboard.insert_text('9800000005');page.keyboard.press('Enter');page.wait_for_function("!document.querySelector('#modal').open");focused(page,'#product-search');assert page.locator('#sale-party').input_value()=='50005'
    page.keyboard.press('F7');focused(page,'#discount');type_current(page,'5.50');page.keyboard.press('Enter');focused(page,'#product-search')
    page.reload();page.wait_for_function("typeof S!=='undefined'&&!!S&&!!document.querySelector('#keyboard-help')");page.keyboard.press('F2');focused(page,'#product-search');assert page.evaluate("cart.reduce((n,l)=>n+l.quantity,0)===78&&Number(window.saleParty)===50005&&Number(window.saleDiscount)===5.5")
    sold=page.evaluate('cart.map(l=>({...l}))');total=page.evaluate('cartTotal()-550')
    page.evaluate("()=>{window.saleCalls=0;const base=window.fetch;window.fetch=async(...args)=>{const r=await base(...args);if(args[0]==='/api/sale'){saleCalls++;await new Promise(done=>setTimeout(done,400));}return r;};}")
    page.keyboard.press('F8');focused(page,'#f-payment');page.keyboard.press('Alt+u');focused(page,'#f-paid');page.keyboard.press('Enter');focused(page,'#f-supply_state');assert len(shop.state()['documents'])==0
    page.keyboard.press('Control+Enter');page.wait_for_function("document.querySelector('#form-submit').disabled");page.keyboard.press('Control+Enter');page.keyboard.press('Escape');assert page.locator('#modal').evaluate('(d)=>d.open');page.wait_for_function("S.documents.length===1&&document.querySelector('.receipt-preview')");assert page.evaluate('saleCalls')==1;bill=shop.state()['documents'][0];assert bill['payment']=='UPI' and bill['total']==total and bill['party_id']==50005
    assert page.evaluate("window.saleParty===''&&window.priceTier==='retail'")
    page.evaluate('()=>{window.printCount=0;window.print=()=>printCount++;}');page.keyboard.press('F10');assert page.evaluate('printCount')==1
    page.keyboard.press('F2');focused(page,'#product-search');assert page.evaluate('cart.length')==0
    # Complete a purchase by scanning, case/fractional quantities, cost and paid amount.
    page.keyboard.press('Alt+4');page.keyboard.press('F4');focused(page,'#f-party_id');page.keyboard.press('Enter');focused(page,'#f-location');page.keyboard.press('Enter');focused(page,'#f-reference');page.keyboard.insert_text('TEST-PURCHASE-001');page.keyboard.press('Enter');focused(page,'[data-purchase-search]')
    page.keyboard.type('8909000000000');page.keyboard.press('Enter');focused(page,'[data-qty]');page.keyboard.press('Alt+c');assert page.locator(':focus').input_value()=='24';page.keyboard.press('Enter');focused(page,'[data-price]');type_current(page,'20');page.keyboard.press('Enter');focused(page,'[data-purchase-search]')
    page.keyboard.press('Shift+Enter');focused(page,'[data-price]');page.keyboard.press('Enter');focused(page,'[data-purchase-search]');page.keyboard.type('TEST ONLY Load Drink 0');page.keyboard.press('ArrowDown');selected=page.locator(':focus').evaluate('(e)=>e.closest(".purchase-line").purchaseChoice');page.wait_for_timeout(100);assert page.locator(':focus').evaluate('(e)=>e.closest(".purchase-line").purchaseChoice')==selected;type_current(page,'8909000000001');page.keyboard.press('Enter');focused(page,'[data-qty]');type_current(page,'2.5');page.keyboard.press('Enter');focused(page,'[data-price]');type_current(page,'22.50');page.keyboard.press('Enter');focused(page,'[data-purchase-search]')
    page.keyboard.press('Alt+p');focused(page,'#f-paid');type_current(page,'500');page.keyboard.press('Control+Enter');page.wait_for_function("S.documents.length===2&&!document.querySelector('#modal').open")
    state=shop.state();purchase=next(d for d in state['documents'] if d['kind']=='purchase');assert purchase['total']==53625 and purchase['paid']==50000;assert next(p for p in state['parties'] if p['id']==supplier)['balance']==3625
    for pid in (10000,10001,11578,19999):
     removed=next((l['quantity'] for l in sold if l['id']==pid),0);added=24 if pid==10000 else 2.5 if pid==10001 else 0
     assert next(p for p in state['products'] if p['id']==pid)['stock']==1000-removed+added
    # Repeated table use is bounded and opens records without mouse clicks.
    page.keyboard.press('Alt+3');assert page.locator('#inventory-results tbody tr').count()==100;page.keyboard.press('PageDown');assert page.evaluate('inventoryOffset')==100
    page.keyboard.press('F3');focused(page,'#inventory-search');page.keyboard.insert_text('LOAD-09999');page.keyboard.press('ArrowDown');focused(page,'#inventory-results tbody button');page.keyboard.press('Enter');focused(page,'#f-name');page.keyboard.press('Enter');focused(page,'#f-sku');page.keyboard.press('Shift+Enter');focused(page,'#f-name');page.keyboard.press('Escape')
    page.keyboard.press('Alt+6');assert page.locator('#people-results tbody tr').count()==100;page.keyboard.press('F3');focused(page,'#people-search');page.keyboard.insert_text('9800000005');page.keyboard.press('ArrowDown');focused(page,'#people-results tbody button');page.keyboard.press('Enter');page.wait_for_function("document.querySelector('#modal').open");page.keyboard.press('Escape')
    assert not errors,errors
    timings['add_median_ms']=statistics.median(timings['add_ms']);frames=timings['scan_to_frame_ms'];timings['scan_frame_p95_ms']=sorted(frames)[int(len(frames)*.95)-1]
    assert timings['add_median_ms']<100 and timings['scan_frame_p95_ms']<500,timings
    if report:Path(report).write_text(json.dumps(timings,indent=2))
    print(json.dumps({k:v for k,v in timings.items() if k!='scan_to_frame_ms'}));print('Heavy keyboard acceptance passed: 10,000 SKUs, 100 consecutive scans, preserved input, safe codes/stock, case and fractional purchases, exact dues/stock, customer/discount/payment shortcuts, Enter navigation, printing and next bill; no JS errors or external requests.');browser.close()
  finally:server.shutdown();server.server_close()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--report');main(parser.parse_args().report)
