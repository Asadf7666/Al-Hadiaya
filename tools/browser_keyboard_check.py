"""Keyboard-only acceptance on isolated desktop and hosted data; no Meta calls."""
import json,sys,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Shop
from desktop_http import DesktopHandler
from staff_access import StaffAccess
from cloud.server import Online,Handler
from playwright.sync_api import sync_playwright

PASSWORD='keyboard-test-password'
def tab_to(page,selector,limit=160):
 for _ in range(limit):
  if page.evaluate('(s)=>document.activeElement.matches(s)',arg=selector):return
  page.keyboard.press('Tab')
 raise AssertionError('Cannot reach with Tab: '+selector+'; focus='+page.evaluate('document.activeElement.outerHTML'))
def type_field(page,selector,text):
 tab_to(page,selector);page.keyboard.press('Control+A');page.keyboard.insert_text(text)
def focused(page,selector):
 try:page.wait_for_function('(s)=>document.activeElement.matches(s)',arg=selector,timeout=10000)
 except Exception as e:raise AssertionError('Expected focus '+selector+'; actual '+str(page.evaluate('({id:document.activeElement.id,tag:document.activeElement.tagName,text:document.activeElement.textContent.slice(0,80),dialog:document.querySelector("#modal").open})'))) from e
def shortcut(page,key,route):
 page.keyboard.press(key);page.wait_for_function('(r)=>page===r',arg=route);focused(page,'#product-search' if key=='F2' else '#main')
def seed(shop):
 shop.act('product',dict(name='Keyboard Cola',sku='KEY-COLA',barcode='8900000000011',category='Cold drinks',kind='stock',unit='bottle',price=50,cost=20,stock=20,location='Warehouse'))
 shop.act('product',dict(name='Keyboard Water',sku='KEY-WATER',category='Water',kind='stock',unit='bottle',price=20,cost=10,stock=20,location='Warehouse'))
 shop.act('party',{'name':'Keyboard Supplier','kind':'supplier'})
def owner_checks(page,shop,hosted=False):
 print('Checking', 'hosted' if hosted else 'desktop',flush=True)
 for key,route in [('Alt+1','overview'),('Alt+2','billing'),('Alt+3','inventory'),('Alt+4','purchases'),('Alt+5','cafe'),('Alt+6','people'),('Alt+7','reports'),('Alt+8','planning'),('Alt+9','orders'),('Alt+0','notifications'),('Alt+s','settings'),('Alt+t','staff')]:shortcut(page,key,route)
 shortcut(page,'Alt+3','inventory');page.keyboard.press('F4');focused(page,'#f-name')
 # Browser validation keeps an empty required form open. Focus remains trapped.
 page.keyboard.press('Control+Enter');assert page.locator('#modal').evaluate('(d)=>d.open')
 for _ in range(32):
  page.keyboard.press('Tab');assert page.evaluate("!!document.activeElement.closest('#modal')"),page.evaluate('document.activeElement.outerHTML')
 page.keyboard.press('Escape');focused(page,'#main')
 # Every primary business form starts at its first editable control.
 for key,route,field in [('Alt+4','purchases','#f-party_id'),('Alt+5','cafe','#f-name'),('Alt+6','people','#f-name'),('Alt+7','reports','#f-name'),('Alt+8','planning','#f-supplier_id'),('Alt+t','staff','#f-name')]:
  shortcut(page,key,route);page.keyboard.press('F4');focused(page,field);page.keyboard.press('Escape');focused(page,'#main')
 # Searchable action chooses a form, saves a profile and restores focus.
 page.keyboard.press('Control+k');focused(page,'#command-query');page.keyboard.insert_text('Add customer');page.keyboard.press('Enter');focused(page,'#f-name')
 page.keyboard.insert_text('Keyboard Customer');page.keyboard.press('Tab');focused(page,'#f-phone');page.keyboard.insert_text('9876543210');page.keyboard.press('Control+Enter');page.wait_for_function("S.parties.some(p=>p.name==='Keyboard Customer')");page.wait_for_function("!document.querySelector('#modal').open")
 page.keyboard.press('Alt+l');focused(page,'#online-location' if hosted else '#node-location');page.keyboard.press('ArrowDown');page.wait_for_function("localLocation()==='Outlet'");page.keyboard.press('ArrowUp');page.wait_for_function("localLocation()==='Warehouse'")
 shortcut(page,'F2','billing');page.keyboard.press('F3');focused(page,'#product-search')
 # Refresh while typing preserves the query and caret instead of moving focus.
 page.keyboard.insert_text('Key');page.evaluate('load()');focused(page,'#product-search');assert page.locator('#product-search').input_value()=='Key'
 page.keyboard.press('ArrowDown');focused(page,'.product-card');names=page.locator('.product-card').all_text_contents();page.keyboard.press('End');assert page.locator(':focus').text_content()==names[-1];page.keyboard.press('Home');assert page.locator(':focus').text_content()==names[0]
 page.keyboard.press('F3');page.keyboard.insert_text('Keyboard Cola');page.keyboard.press('ArrowDown');focused(page,'.product-card')
 page.keyboard.press('Enter');page.wait_for_function('cart.length===1');focused(page,'.product-card');page.keyboard.press('Enter');page.wait_for_function('cart[0].quantity===2');focused(page,'.product-card')
 # Native selectors, quantity, category arrow navigation and scanner Enter work.
 page.keyboard.press('F3');page.keyboard.press('Control+A');page.keyboard.insert_text('8900000000011');page.keyboard.press('Enter');page.wait_for_function('cart[0].quantity===3');focused(page,'#product-search');assert page.locator('#product-search').input_value()==''
 page.keyboard.press('Tab');focused(page,'.tabs button[aria-selected=true]');page.keyboard.press('ArrowRight');focused(page,'.tabs button[aria-selected=true]');page.keyboard.press('Home');page.wait_for_function("category==='All'")
 page.keyboard.press('F8');focused(page,'#f-payment');page.keyboard.press('ArrowDown');page.keyboard.press('Tab');focused(page,'#f-paid');page.keyboard.press('Control+Enter');page.wait_for_function('S.documents.length===1');page.wait_for_function("document.querySelector('#dialog-title').textContent==='Invoice details'")
 assert shop.state()['documents'][0]['payment']=='UPI';assert next(p for p in shop.state()['products'] if p['sku']=='KEY-COLA')['stock']==17
 page.keyboard.press('Escape');page.keyboard.press('F9');focused(page,'#invoice-search');page.keyboard.insert_text(shop.state()['documents'][0]['id']);assert page.locator('#invoice-results tbody tr').count()==1;page.keyboard.press('Escape')
 # Escape returns to the invoking control; Help exposes a labelled dialog.
 tab_to(page,'#keyboard-help');page.keyboard.press('Enter');focused(page,'#dialog-title');page.keyboard.press('Escape');focused(page,'#keyboard-help')
 shortcut(page,'Alt+s','settings');type_field(page,'#f-name','Keyboard Shop');page.keyboard.press('Control+Enter');page.wait_for_function("S.settings.name==='Keyboard Shop'");focused(page,'#f-name')
 if not hosted:
  # Permanent retirement stays usable without the server and without a mouse.
  with shop.connect() as db:db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps('https://retired.example.test'),'cloud_url'))
  page.evaluate('load()');page.wait_for_function("!!document.querySelector('[onclick=\"retireServerForm()\"]')")
  tab_to(page,'[onclick="retireServerForm()"]');page.keyboard.press('Enter');focused(page,'#f-confirm');page.keyboard.insert_text('RETIRED');page.keyboard.press('Control+Enter');page.wait_for_function("!S.settings.cloud_url&&!document.querySelector('#modal').open");assert len(shop.state()['documents'])==1
 # Offscreen mobile navigation is skipped, but keyboard can open and close it.
 page.set_viewport_size({'width':700,'height':850});page.wait_for_function("document.querySelector('.sidebar').inert")
 page.keyboard.press('Alt+n');focused(page,'#nav button');assert not page.locator('.sidebar').evaluate('(e)=>e.inert');page.keyboard.press('Escape');focused(page,'#mobile-menu');assert page.locator('.sidebar').evaluate('(e)=>e.inert')
 page.keyboard.press('Control+k');focused(page,'#command-query');page.keyboard.insert_text('Inventory');page.keyboard.press('Enter');page.wait_for_function("page==='inventory'");focused(page,'#main')
 page.set_viewport_size({'width':1400,'height':1000})

def main():
 with tempfile.TemporaryDirectory() as folder:
  local=Shop(Path(folder)/'local');seed(local);DesktopHandler.shop=local
  desktop=ThreadingHTTPServer(('127.0.0.1',0),DesktopHandler);desktop.access=StaffAccess(local.folder,'http://localhost',False,local=True,shop=local)
  web=Online(Path(folder)/'web','http://localhost',False);seed(web.shop);web.user({'username':'owner','password':PASSWORD,'role':'owner'})
  hosted=ThreadingHTTPServer(('127.0.0.1',0),Handler);hosted.online=web;web.origin='http://127.0.0.1:'+str(hosted.server_port)
  for server in (desktop,hosted):threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox']);errors=[]
    for server,shop,is_web in [(desktop,local,False),(hosted,web.shop,True)]:
     page=browser.new_page(viewport={'width':1400,'height':1000});page.on('pageerror',lambda e:errors.append(e.stack))
     page.add_init_script("const normalFetch=window.fetch;window.fetch=async(...args)=>{const response=await normalFetch(...args);if(['/api/users','/api/peers'].includes(args[0]))await new Promise(done=>setTimeout(done,250));return response;}")
     page.route('**/*',lambda r:r.continue_() if r.request.url.startswith(('http://127.0.0.1:','http://localhost:')) else r.abort())
     origin='http://127.0.0.1:'+str(server.server_port);page.goto(origin+('/app' if is_web else '/'));focused(page,'#login-username');page.keyboard.insert_text('owner');page.keyboard.press('Tab');focused(page,'#login-password');page.keyboard.insert_text(PASSWORD);page.keyboard.press('Enter');page.wait_for_function("typeof S!=='undefined'&&!!S&&!!document.querySelector('#keyboard-help')")
     owner_checks(page,shop,is_web);page.close()
    # Permissions apply to keyboard commands exactly as they do to the UI.
    desktop.access.user({'username':'cashier','password':PASSWORD,'role':'cashier','location':'Warehouse'})
    page=browser.new_page();page.on('pageerror',lambda e:errors.append(e.stack));page.goto('http://127.0.0.1:'+str(desktop.server_port)+'/login');focused(page,'#login-username');page.keyboard.insert_text('cashier');page.keyboard.press('Tab');page.keyboard.insert_text(PASSWORD);page.keyboard.press('Enter');page.wait_for_function("typeof S!=='undefined'&&S?.web_user?.role==='cashier'")
    page.keyboard.press('Alt+3');assert page.evaluate('page')=='overview';page.keyboard.press('Control+k');focused(page,'#command-query');page.keyboard.insert_text('Add product');assert page.locator('#command-results button').count()==0;page.keyboard.press('Escape');shortcut(page,'Alt+t','staff');page.keyboard.press('F4');assert not page.locator('#modal').evaluate('(d)=>d.open')
    assert not errors,errors;browser.close()
   print('Keyboard-only desktop and hosted acceptance passed: all pages, primary forms, validation/focus trap, product grid/barcodes, UPI checkout/exact stock, profiles, settings, retired-server recovery, mobile navigation and cashier restrictions; no JS errors or external messaging.')
  finally:
   for server in (desktop,hosted):server.shutdown();server.server_close()
if __name__=='__main__':main()
