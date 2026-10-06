"""Windows CI: execute the installer, authenticate, bill, update and preserve data."""
import http.cookiejar,json,os,pathlib,sqlite3,subprocess,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
 if os.name!='nt':raise SystemExit('Run this check on Windows.')
 root=pathlib.Path(os.environ['RUNNER_TEMP'])/'alhadiya-v1-check';root.mkdir(exist_ok=True)
 install=root/'installed';data=root/'shop-data';env={**os.environ,'AL_HIDAYA_DATA':str(data)}
 version=(ROOT/'VERSION').read_text().strip();setup=ROOT/'dist'/('AlHidayaTraders-Setup-'+version+'.exe')
 def installer():subprocess.run([str(setup),'/S','/D='+str(install)],env=env,check=True,timeout=240)
 def start():
  process=subprocess.Popen([str(install/'runtime/python.exe'),str(install/'app.py'),'--no-browser'],env=env,stdout=subprocess.DEVNULL,stderr=None)
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
  with client.open(origin+'/keyboard.js',timeout=10) as response:
   assert b'Find a page or action' in response.read(), 'Installed keyboard module missing.'
  with client.open(origin+'/',timeout=10) as response:assert b'/keyboard.js' in response.read()
  pid=act('product',{'name':'CI Drink','sku':'CI-DRINK','category':'Cold drinks','kind':'stock','unit':'bottle','price':50,'cost':20,'stock':5,'location':'Warehouse'})['id']
  sale={'location':'Warehouse','items':[{'product_id':pid,'quantity':1}]};assert act('sale',sale,'a'*32)==act('sale',sale,'a'*32)
  installer();process.wait(timeout=30);process=start();token=sign_in('/login')
  with client.open(origin+'/api/state') as response:state=json.load(response)
  assert len(state['documents'])==1 and state['products'][0]['stock']==4
  subprocess.run([str(install/'runtime/python.exe'),str(install/'packaging/maintenance.py')],env=env,check=True,timeout=60);process.wait(timeout=30)
  subprocess.run([str(install/'Uninstall.exe'),'/S'],env=env,check=True,timeout=120)
  assert (data/'shop.sqlite3').exists() and list((data/'backups').glob('*.sqlite3'))
  with sqlite3.connect(data/'shop.sqlite3') as db:assert db.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()[0]==4
  print('Windows installer execution, offline owner setup, retry-safe billing, in-place update, account/data retention and uninstall preservation passed.')
 finally:
  if process.poll() is None:process.kill();process.wait(timeout=20)
if __name__=='__main__':main()
