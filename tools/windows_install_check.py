"""Windows CI: execute the installer, authenticate, bill, update and preserve data."""
import http.cookiejar,json,os,pathlib,sqlite3,subprocess,time,urllib.error,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
 if os.name!='nt':raise SystemExit('Run this check on Windows.')
 root=pathlib.Path(os.environ['RUNNER_TEMP'])/'alhadiya-v1-check';root.mkdir(exist_ok=True)
 install=root/'installed';data=root/'shop-data';env={**os.environ,'AL_HIDAYA_DATA':str(data)}
 version=(ROOT/'VERSION').read_text().strip();setup=ROOT/'dist'/('AlHidayaTraders-Setup-'+version+'.exe')
 def installer():subprocess.run([str(setup),'/S','/D='+str(install)],env=env,check=True,timeout=240)
 def start():
  process=subprocess.Popen([str(install/'app/AlHidayaTraders.exe'),'--no-browser'],env=env,stdout=subprocess.DEVNULL,stderr=None)
  for _ in range(100):
   if process.poll() is not None:raise RuntimeError('Installed app exited before serving.')
   try:
    with urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=1) as response:assert json.load(response)['version']==version
    return process
   except OSError:time.sleep(.2)
  process.kill();raise RuntimeError('Installed app did not start.')
 installer();process=start();origin='http://127.0.0.1:8765';cookies=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(cookies))
 def sign_in(path):
  req=urllib.request.Request(origin+path,data=b'username=owner&password=ci-owner-test-password',headers={'Origin':origin})
  with client.open(req,timeout=20) as response:response.read()
  with client.open(origin+'/api/session',timeout=10) as response:return json.load(response)['token']
 def act(action,body,key=''):
  req=urllib.request.Request(origin+'/api/'+action,data=json.dumps(body).encode(),headers={'Origin':origin,'Content-Type':'application/json','X-Shop-Token':token,'X-Request-ID':key})
  with client.open(req,timeout=20) as response:return json.load(response)
 try:
  token=sign_in('/setup')
  assert not [p for p in install.rglob('*') if p.suffix in ('.py','.pyc')] and not (install/'runtime').exists(), 'Installed app must be the native program only.'
  with client.open(origin+'/license.js',timeout=10) as response:assert b'licencePage' in response.read(), 'Installed licence module missing.'
  with client.open(origin+'/api/state',timeout=10) as response:licence=json.load(response)['licence']
  assert licence['status']=='trial' and licence['writable'] and len(licence['installation_id'])==19, 'A fresh installation must start its trial.'
  try:act('licence_install',{'text':'not a licence'});raise AssertionError('A forged licence was accepted.')
  except urllib.error.HTTPError as error:assert error.code==400
  with client.open(origin+'/keyboard.js',timeout=10) as response:
   assert b'Find a page or action' in response.read(), 'Installed keyboard module missing.'
  with client.open(origin+'/',timeout=10) as response:assert b'/keyboard.js' in response.read()
  pid=act('product',{'name':'CI Drink','sku':'CI-DRINK','category':'Cold drinks','kind':'stock','unit':'bottle','price':50,'cost':20,'stock':5,'location':'Warehouse'})['id']
  supplier=act('party',{'name':'CI Supplier','kind':'supplier'})['id'];act('purchase',{'party_id':supplier,'location':'Warehouse','reference':'CI-1','paid':0,'items':[{'product_id':pid,'quantity':2,'price':20,'lot':'CI-LOT','expiry':'2099-12-31'}]},'b'*32)
  with client.open(origin+'/api/state',timeout=10) as response:assert [(l['lot'],l['quantity']) for l in json.load(response)['lots']]==[('CI-LOT',2)], 'Purchase lot was not recorded.'
  sale={'location':'Warehouse','items':[{'product_id':pid,'quantity':1}]};assert act('sale',sale,'a'*32)==act('sale',sale,'a'*32)
  sold=act('sale',sale,'a'*32)['id'];note=act('return',{'id':sold,'reason':'CI return','items':[{'line':0,'quantity':1}]},'c'*32);assert note['refund']==5000
  act('shift_open',{'opening_float':100});assert act('shift_close',{'counted':100})['difference']==0
  installer();process.wait(timeout=30);process=start();token=sign_in('/login')
  with client.open(origin+'/api/state') as response:state=json.load(response)
  assert sorted(d['kind'] for d in state['documents'])==['purchase','sale','sale_return'] and state['products'][0]['stock']==7 and state['lots'][0]['quantity']==2 and len(state['shifts'])==1
  subprocess.run([str(install/'app/AlHidayaTraders.exe'),'--maintenance'],env=env,check=True,timeout=60);process.wait(timeout=30)
  subprocess.run([str(install/'Uninstall.exe'),'/S'],env=env,check=True,timeout=120)
  assert (data/'shop.sqlite3').exists() and list((data/'backups').glob('*.sqlite3'))
  with sqlite3.connect(data/'shop.sqlite3') as db:assert db.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()[0]==7
  print('Windows installer execution, native compiled install, trial licence, offline owner setup, retry-safe billing, in-place update, account/data retention and uninstall preservation passed.')
 finally:
  if process.poll() is None:process.kill();process.wait(timeout=20)
if __name__=='__main__':main()
