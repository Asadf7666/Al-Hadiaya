"""Optional Playwright acceptance check; isolated data and no Meta requests."""
import os,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Shop
from desktop_http import DesktopHandler
from staff_access import StaffAccess
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
def main():
 with tempfile.TemporaryDirectory() as folder:
  shop=Shop(folder)
  milk=shop.act('product',dict(name='Milk',sku='MILK',category='Ingredients',kind='ingredient',unit='ml',cost=.06,stock=500,location='Warehouse'))['id']
  coffee=shop.act('product',dict(name='Coffee',sku='COFFEE',category='Coffee',kind='recipe',unit='cup',price=80,stock=0))['id']
  shop.act('recipe',{'product_id':coffee,'items':[{'ingredient_id':milk,'quantity':150}]});shop.act('transfer',{'product_id':milk,'quantity':300,'source':'Warehouse','target':'Outlet'})
  shop.act('product',dict(name='Cola',sku='COLA',category='Cold drinks',kind='stock',unit='bottle',price=50,stock=5,location='Outlet'))
  DesktopHandler.shop=shop;server=ThreadingHTTPServer(('127.0.0.1',0),DesktopHandler);server.access=StaffAccess(folder,'http://localhost',False,local=True,shop=shop)
  threading.Thread(target=server.serve_forever,daemon=True).start();origin='http://127.0.0.1:'+str(server.server_port)
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(origin);page.locator('[name=username]').fill('owner');page.locator('[name=password]').fill('owner-test-password');page.get_by_role('button',name='Create owner account').click();page.wait_for_function('!!S')
    page.get_by_role('button',name='Café menu',exact=True).click();page.get_by_role('button',name='Open café POS',exact=True).click();page.wait_for_function("category==='Café menu'&&localLocation()==='Outlet'")
    cards=page.locator('.product-card');assert cards.count()==1;cards.first.click();cards.first.click();page.get_by_role('button',name='Checkout & save bill').click();page.locator('#f-payment').select_option('UPI');page.get_by_role('button',name='Save invoice',exact=True).click();page.wait_for_function('S.documents.length===1')
    page.wait_for_function("!!document.querySelector('#modal .receipt-preview')");page.keyboard.press('F2');page.wait_for_function("document.activeElement.id==='product-search'&&!document.querySelector('#modal').open");assert page.evaluate("category==='Café menu'&&localLocation()==='Outlet'&&cart.length===0")
    state=shop.state();bill=state['documents'][0];assert bill['total']==16000 and bill['location']=='Outlet' and bill['party_id'] is None
    quantities={r['location']:r['quantity'] for r in state['stocks'] if r['product_id']==milk};assert quantities=={'Warehouse':200,'Outlet':0};assert not errors,errors;browser.close()
   print('Café POS passed: owner switches to Outlet, café-only filter, two coffees, walk-in UPI invoice and exact recipe consumption; no JS errors.')
  finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
