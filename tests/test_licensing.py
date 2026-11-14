import datetime as dt,json,secrets,tempfile,unittest,urllib.error,urllib.request,http.cookiejar,threading
from http.server import ThreadingHTTPServer
from pathlib import Path
import licensing
from licensing import Licence,LicenceRequired,DAY,TRIAL_DAYS,GRACE_DAYS

class Clock:
    def __init__(self):self.t=dt.datetime(2026,11,14,12).timestamp()
    def __call__(self):return self.t
    def days(self,n):self.t+=n*DAY

class LicensingTest(unittest.TestCase):
    def setUp(self):
        self.seed=secrets.token_bytes(32);self.real=licensing.PUBLIC_KEY
        licensing.PUBLIC_KEY=licensing.public_key(self.seed).hex()
        self.tmp=tempfile.TemporaryDirectory();self.clock=Clock();self.machine='1A2B-3C4D-5E6F-7A8B'
        self.lic=Licence(self.tmp.name,machine=self.machine,clock=self.clock)
    def tearDown(self):
        licensing.PUBLIC_KEY=self.real;self.tmp.cleanup()
    def issue(self,expires='2027-11-14',machine=None,seed=None,**extra):
        return licensing.pack({'v':1,'product':licensing.PRODUCT,'id':'AHT-TEST','customer':'Test Shop','edition':'Standard','issued':'2026-11-14','expires':expires,'machine':machine or self.machine,**extra},seed or self.seed)

    def test_rfc8032_vector_and_rejection_of_altered_signatures(self):
        seed=bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
        public=bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
        signature=bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
        self.assertEqual(licensing.public_key(seed),public);self.assertEqual(licensing.sign(seed,b''),signature)
        self.assertTrue(licensing.verify(public,b'',signature))
        for index in (0,31,32,63):
            bad=bytearray(signature);bad[index]^=1;self.assertFalse(licensing.verify(public,b'',bytes(bad)))
        self.assertFalse(licensing.verify(public,b'x',signature))
        # A non-canonical s (s + L) must not verify.
        s=int.from_bytes(signature[32:],'little')+licensing._L
        self.assertFalse(licensing.verify(public,b'',signature[:32]+s.to_bytes(32,'little')))
        self.assertFalse(licensing.verify(b'\x00'*31,b'',signature));self.assertFalse(licensing.verify(public,b'',b''))

    def test_trial_counts_down_then_becomes_read_only(self):
        s=self.lic.status();self.assertEqual((s['status'],s['trial_days_left'],s['writable'],s['warn']),('trial',TRIAL_DAYS,True,False))
        self.clock.days(50);s=self.lic.status();self.assertEqual((s['trial_days_left'],s['warn']),(10,True))
        self.clock.days(10);s=self.lic.status();self.assertEqual((s['status'],s['writable']),('unlicensed',False))
        with self.assertRaises(LicenceRequired):self.lic.require('sale')
        for action in ('backup','logout','shutdown','licence_install','staff_password'):self.lic.require(action)

    def test_trial_survives_restart_and_clock_rollback(self):
        self.clock.days(59);self.assertEqual(self.lic.status()['trial_days_left'],1)
        self.clock.days(5);self.assertFalse(self.lic.status()['writable'])
        self.clock.days(-40)
        self.assertFalse(self.lic.status()['writable'],'Setting the PC date back must not revive the trial.')
        again=Licence(self.tmp.name,machine=self.machine,clock=self.clock)
        self.assertFalse(again.status()['writable'])

    def test_edited_trial_record_ends_the_trial(self):
        record=Path(self.tmp.name)/'licence'/'state.json';data=json.loads(record.read_text())
        self.clock.days(70);data['first_run']=int(self.clock.t);record.write_text(json.dumps(data))
        self.assertEqual(Licence(self.tmp.name,machine=self.machine,clock=self.clock).status()['status'],'unlicensed')

    def test_valid_licence_unlocks_and_expires_with_grace(self):
        self.clock.days(90);self.assertFalse(self.lic.status()['writable'])
        s=self.lic.install(self.issue(expires='2027-06-30'))
        self.assertEqual((s['status'],s['writable'],s['customer'],s['licence_id']),('licensed',True,'Test Shop','AHT-TEST'))
        self.lic.require('sale')
        self.clock.t=dt.datetime(2027,6,30,23).timestamp();self.assertEqual(self.lic.status()['status'],'licensed')
        self.clock.t=dt.datetime(2027,7,3,12).timestamp();s=self.lic.status();self.assertEqual((s['status'],s['writable']),('grace',True))
        self.clock.t=dt.datetime(2027,6,30,12).timestamp()+(GRACE_DAYS+2)*DAY;s=self.lic.status();self.assertEqual((s['status'],s['writable']),('expired',False))
        with self.assertRaises(LicenceRequired):self.lic.require('sale')
        s=self.lic.install(self.issue(expires=None));self.assertEqual((s['status'],s['days_left']),('licensed',None))
        self.clock.days(5000);self.assertTrue(self.lic.status()['writable'])

    def test_forged_altered_foreign_and_wrong_pc_licences_are_refused(self):
        good=self.issue()
        cases={'forged':self.issue(seed=secrets.token_bytes(32)),'other pc':self.issue(machine='0000-0000-0000-0001'),
               'other product':self.issue(product='something-else'),'expired':self.issue(expires='2026-01-01'),
               'garbage':'hello','empty':'','no signature':good.split('.')[0]}
        body,signature=''.join(good.splitlines()[1:-1]).split('.')
        payload=json.loads(licensing._unb64(body));payload['expires']='2099-01-01'
        cases['altered']=licensing._b64(json.dumps(payload,sort_keys=True,separators=(',',':')).encode())+'.'+signature
        for name,text in cases.items():
            with self.subTest(name),self.assertRaises(ValueError):self.lic.install(text)
        for value in (None,5,['x'],'x'*30000):
            with self.assertRaises(ValueError):self.lic.install(value)
        self.assertEqual(self.lic.status()['status'],'trial')
        # A licence file copied into place from another PC is ignored, not trusted.
        (Path(self.tmp.name)/'licence'/'licence.lic').write_text(cases['other pc'])
        fresh=Licence(self.tmp.name,machine=self.machine,clock=self.clock).status()
        self.assertEqual(fresh['status'],'trial');self.assertIn('another PC',fresh['problem'])

    def test_unbound_licence_and_removal(self):
        self.assertEqual(self.lic.install(self.issue(machine='*'))['status'],'licensed')
        self.assertEqual(self.lic.remove()['status'],'trial')
        self.assertEqual(len(licensing.machine_id()),19);self.assertEqual(licensing.machine_id(),licensing.machine_id())

    def test_shipped_public_key_rejects_keys_it_did_not_sign(self):
        licensing.PUBLIC_KEY=self.real
        with self.assertRaises(ValueError):licensing.parse(self.issue())

class DesktopLicenceTest(unittest.TestCase):
    def setUp(self):
        from app import Shop
        from desktop_http import DesktopHandler
        from staff_access import StaffAccess
        self.seed=secrets.token_bytes(32);self.real=licensing.PUBLIC_KEY;licensing.PUBLIC_KEY=licensing.public_key(self.seed).hex()
        self.tmp=tempfile.TemporaryDirectory();self.clock=Clock();self.shop=Shop(self.tmp.name)
        handler=type('Handler',(DesktopHandler,),{'shop':self.shop})
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        self.server.access=StaffAccess(self.tmp.name,'http://localhost',False,local=True,shop=self.shop)
        self.server.licence=Licence(self.tmp.name,machine='1A2B-3C4D-5E6F-7A8B',clock=self.clock)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.origin=f'http://127.0.0.1:{self.server.server_port}'
        self.server.access.user({'username':'owner','password':'owner-password-123','role':'owner','location':'Warehouse'})
        self.server.access.user({'username':'boss','password':'manager-password-123','role':'manager','location':'Warehouse'})
    def tearDown(self):
        self.server.shutdown();self.server.server_close();licensing.PUBLIC_KEY=self.real;self.tmp.cleanup()
    def client(self,username,password):
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        opener.open(urllib.request.Request(self.origin+'/login',data=f'username={username}&password={password}'.encode(),headers={'Origin':self.origin})).read()
        token=json.load(opener.open(self.origin+'/api/session'))['token']
        def act(action,body=None):
            request=urllib.request.Request(self.origin+'/api/'+action,data=json.dumps(body or {}).encode(),headers={'Origin':self.origin,'X-Shop-Token':token})
            try:
                with opener.open(request) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as error:return error.code,json.load(error)
        return opener,act
    def test_lapsed_installation_is_read_only_until_the_owner_installs_a_licence(self):
        opener,act=self.client('owner','owner-password-123')
        product={'name':'Tea','sku':'TEA','category':'Drinks','kind':'stock','unit':'pc','price':10,'cost':5,'stock':3,'location':'Warehouse'}
        self.assertEqual(act('product',product)[0],200)
        self.clock.days(TRIAL_DAYS+1)
        state=json.load(opener.open(self.origin+'/api/state'))
        self.assertEqual(state['licence']['status'],'unlicensed');self.assertEqual(len(state['products']),1)
        for action,body in (('product',{**product,'sku':'TEA2'}),('settings',{'name':'X'}),('restore_bundle',{}),('location',{'location':'Outlet'}),('sale',{'location':'Warehouse','items':[]})):
            code,result=act(action,body);self.assertEqual(code,402,action);self.assertTrue(result['licence'])
        self.assertEqual(act('backup')[0],200)
        self.assertEqual(json.load(opener.open(self.origin+'/api/state'))['settings']['name'],'Al Hadiya Traders')
        text=licensing.pack({'v':1,'product':licensing.PRODUCT,'id':'AHT-1','customer':'Shop','issued':'2026-11-14','expires':None,'machine':'1A2B-3C4D-5E6F-7A8B'},self.seed)
        _,manager=self.client('boss','manager-password-123')
        self.assertEqual(manager('licence_install',{'text':text})[0],403)
        self.assertEqual(manager('licence_remove')[0],403)
        self.assertEqual(act('licence_install',{'text':'forged'})[0],400)
        self.assertEqual(act('licence_install',{})[0],400)
        code,status=act('licence_install',{'text':text});self.assertEqual((code,status['status']),(200,'licensed'))
        self.assertEqual(act('product',{**product,'sku':'TEA2'})[0],200)
        with self.shop.connect() as db:self.assertTrue(db.execute("SELECT 1 FROM audit WHERE action='licence_install'").fetchone())
    def test_licence_script_needs_a_session(self):
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.assertIn('/login',opener.open(self.origin+'/license.js').geturl())

if __name__=='__main__':unittest.main()

class CounterAccessTest(DesktopLicenceTest):
    def test_returns_need_a_manager_and_a_valid_licence(self):
        self.server.access.user({'username':'till','password':'cashier-password-123','role':'cashier','location':'Warehouse'})
        self.server.access.user({'username':'look','password':'viewer-password-1234','role':'viewer','location':'Warehouse'})
        _,owner=self.client('owner','owner-password-123')
        pid=owner('product',{'name':'<img src=x onerror=alert(1)>','sku':'X1','category':'Drinks','kind':'stock','unit':'pc','price':10,'cost':5,'stock':5,'location':'Warehouse'})[1]['id']
        sale=owner('sale',{'location':'Warehouse','items':[{'product_id':pid,'quantity':2}]})[1]['id']
        body={'id':sale,'reason':'x','items':[{'line':0,'quantity':1}]}
        _,cashier=self.client('till','cashier-password-123');_,viewer=self.client('look','viewer-password-1234')
        self.assertEqual(cashier('return',body)[0],403);self.assertEqual(viewer('return',body)[0],403)
        self.assertEqual(cashier('stock_count',{'location':'Warehouse','counts':[{'product_id':pid,'counted':0}]})[0],403)
        self.assertEqual(viewer('shift_open',{'opening_float':1})[0],403)
        self.assertEqual(cashier('shift_open',{'opening_float':100})[0],200)
        for bad in ({'id':"x' OR '1'='1",'reason':'x','items':[{'line':0,'quantity':1}]},{'id':sale,'reason':'x','items':[{'line':-1,'quantity':1}]},{'id':sale,'reason':'x','items':[{'line':0,'quantity':-5}]},{'id':sale,'reason':'x','refund':-1,'items':[{'line':0,'quantity':1}]},{'id':sale,'reason':'x','items':'nope'}):
            self.assertEqual(owner('return',bad)[0],400,bad)
        self.clock.days(TRIAL_DAYS+1)
        for action,payload in (('return',body),('stock_count',{'location':'Warehouse','counts':[]}),('shift_close',{'counted':1})):
            self.assertEqual(owner(action,payload)[0],402,action)
