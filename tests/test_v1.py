import base64,io,json,tempfile,threading,unittest,urllib.request,urllib.error,zipfile
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from app import Shop
from staff_access import StaffAccess
from desktop_http import DesktopHandler
from backup_bundle import bundle,restore

class V1Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.shop=Shop(self.tmp.name);self.access=StaffAccess(self.tmp.name,'http://localhost',False,local=True,shop=self.shop)
  self.access.user({'username':'owner','password':'owner-test-password','role':'owner'})
  self.pid=self.shop.act('product',dict(name='Cola',sku='COLA',category='Cold drinks',unit='bottle',kind='stock',price=50,cost=20,stock=100,location='Warehouse'))['id']
 def tearDown(self):self.tmp.cleanup()
 def test_retried_bill_is_atomic_and_reusing_key_with_different_data_fails(self):
  data={'location':'Warehouse','items':[{'product_id':self.pid,'quantity':2}],'_request_id':'a'*32,'_request_actor':'1:owner'}
  first=self.shop.act('sale',data);second=self.shop.act('sale',data)
  self.assertEqual(first,second);self.assertEqual(len(self.shop.state()['documents']),1);self.assertEqual(self.shop.state()['products'][0]['stock'],98)
  with self.assertRaisesRegex(ValueError,'another operation'):self.shop.act('sale',{**data,'items':[{'product_id':self.pid,'quantity':3}]})
 def test_failed_bill_does_not_reserve_retry_key(self):
  data={'location':'Warehouse','items':[{'product_id':self.pid,'quantity':101}],'_request_id':'a'*32}
  with self.assertRaises(ValueError):self.shop.act('sale',data)
  with self.shop.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM operation_requests').fetchone()[0],0)
 def test_final_disconnect_preserves_identity_and_rejects_pending_changes(self):
  from cloud_sync import disconnect,DDL
  before=self.shop.state()['settings']['device_id']
  with self.shop.connect() as db:
   db.executescript(DDL);db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps('https://example.test'),'cloud_url'))
  with patch('cloud_sync._sync_desktop',return_value={'pending':1,'more':False}):
   with self.assertRaises(ValueError):disconnect(self.shop,{'confirm':'DISCONNECT'})
  self.assertTrue(self.shop.state()['settings']['cloud_url'])
  with patch('cloud_sync._sync_desktop',return_value={'pending':0,'more':False}):disconnect(self.shop,{'confirm':'DISCONNECT'})
  self.assertEqual(self.shop.state()['settings']['cloud_url'],'');self.assertEqual(self.shop.state()['settings']['device_id'],before)
 def test_automatic_retention_keeps_manual_backup_and_recent_history(self):
  from backup_retention import prune
  folder=self.shop.folder/'backups';folder.mkdir(exist_ok=True)
  for day in range(1,11):
   for hour in range(10):
    p=folder/f'AlHidaya-Auto-202609{day:02d}-{hour:02d}0000-000000.sqlite3';p.touch();p.with_suffix('.media').mkdir()
  manual=folder/'AlHidaya-20260901-000000-000000.sqlite3';manual.touch();prune(folder)
  self.assertTrue(manual.exists());self.assertTrue((folder/'AlHidaya-Auto-20260910-090000-000000.sqlite3').exists());self.assertFalse((folder/'AlHidaya-Auto-20260901-000000-000000.media').exists());self.assertLessEqual(len(list(folder.glob('AlHidaya-Auto-*.sqlite3'))),15)
 def test_backup_bundle_preserves_photos_and_local_accounts(self):
  photo=self.shop.folder/'media'/'example.png';photo.parent.mkdir(exist_ok=True);photo.write_bytes(b'original-photo')
  with self.shop.connect() as db:account_material=tuple(db.execute('SELECT salt,password_hash FROM web_users').fetchone())
  raw=bundle(self.shop);self.shop.act('adjust',{'product_id':self.pid,'location':'Warehouse','quantity':-50,'note':'Test change'})
  photo.write_bytes(b'changed-photo')
  restore(self.shop,{'confirm':'RESTORE','content':base64.b64encode(raw).decode()})
  self.assertEqual(self.shop.state()['products'][0]['stock'],100);self.assertIsNotNone(self.access.login('owner','owner-test-password','test'))
  self.assertEqual(photo.read_bytes(),b'original-photo')
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   self.assertFalse(any('credential' in n for n in z.namelist()))
   for material in account_material:self.assertNotIn(material.encode(),z.read('shop.sqlite3'))
 def test_backup_zip_traversal_rejected_without_changing_stock(self):
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:z.writestr('../escape.txt','bad')
  with self.assertRaisesRegex(ValueError,'Unsafe'):restore(self.shop,{'confirm':'RESTORE','content':base64.b64encode(raw.getvalue()).decode()})
  self.assertEqual(self.shop.state()['products'][0]['stock'],100)
 def test_restore_failure_rolls_back_database_and_photos(self):
  raw=bundle(self.shop);self.shop.act('adjust',{'product_id':self.pid,'location':'Warehouse','quantity':-50,'note':'Change'})
  with patch('staff_access.StaffAccess',side_effect=RuntimeError('Storage failed')):
   with self.assertRaisesRegex(ValueError,'Previous records were restored'):restore(self.shop,{'confirm':'RESTORE','content':base64.b64encode(raw).decode()})
  self.assertEqual(self.shop.state()['products'][0]['stock'],50);self.assertIsNotNone(self.access.login('owner','owner-test-password','rollback'))
 def test_purchase_order_retry_does_not_create_duplicate_order(self):
  supplier=self.shop.act('party',{'name':'Supplier','kind':'supplier'})['id']
  data={'supplier_id':supplier,'location':'Warehouse','items':[{'product_id':self.pid,'quantity':24,'price':20}],'_request_id':'b'*32}
  self.assertEqual(self.shop.act('purchase_order_create',data),self.shop.act('purchase_order_create',data));self.assertEqual(len(self.shop.state()['purchase_orders']),1)
 def test_restricted_sender_pauses_remaining_batch(self):
  from notifications import process_outbox
  self.shop.act('whatsapp_settings',{'whatsapp_enabled':True,'whatsapp_phone_id':'123','whatsapp_api_version':'v26.0','whatsapp_daily_time':'00:00','whatsapp_internal_template':'internal'})
  for phone in ('9876543210','9876543211'):self.shop.act('internal_contact',{'name':'Staff','phone':phone,'opt_in':True})
  self.shop.daily_update()
  with self.shop.connect() as db:
   import datetime as dt
   db.execute('INSERT INTO whatsapp_templates(name,language,status,category,body,supported,checked) VALUES(?,?,?,?,?,?,?)',('internal','en','APPROVED','UTILITY','{{1}} {{2}} {{3}}',1,dt.datetime.now(dt.timezone.utc).isoformat()))
  with patch('whatsapp_policy.sender_ready',return_value=(True,'')),patch('notifications.read_token',return_value='test-only'),patch('notifications.deliver',return_value=('restricted','Meta restricted sender','')) as send:
   process_outbox(self.shop);process_outbox(self.shop);self.assertEqual(send.call_count,1)
  state=self.shop.state();self.assertFalse(state['settings']['whatsapp_enabled']);self.assertTrue(state['settings']['whatsapp_pause_reason']);self.assertTrue(any(n['status']=='queued' for n in state['notifications']))
 def test_staff_password_reset_revokes_sessions_and_cashier_cannot_admin(self):
  self.access.user({'username':'cashier','password':'cashier-test-password','role':'cashier'})
  token=self.access.login('cashier','cashier-test-password','test');user=self.access.session('ah_session='+token)
  with self.assertRaises(PermissionError):self.access.act(user,'adjust',{})
  self.assertEqual(self.access.state(user)['purchase_orders'],[])
  self.access.password({'id':user['id'],'password':'new-cashier-password'})
  self.assertIsNone(self.access.session('ah_session='+token));self.assertIsNotNone(self.access.login('cashier','new-cashier-password','test'))
 def test_local_http_requires_login_and_csrf_and_preserves_retry_id(self):
  DesktopHandler.shop=self.shop;server=ThreadingHTTPServer(('127.0.0.1',0),DesktopHandler);server.access=self.access
  threading.Thread(target=server.serve_forever,daemon=True).start();origin='http://127.0.0.1:'+str(server.server_port)
  try:
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(origin+'/api/state')
   self.assertEqual(e.exception.code,401);e.exception.close()
   token=self.access.login('owner','owner-test-password','test');user=self.access.session('ah_session='+token);headers={'Origin':origin,'Cookie':'ah_session='+token,'Content-Type':'application/json','X-Request-ID':'a'*32}
   data=json.dumps({'location':'Warehouse','items':[{'product_id':self.pid,'quantity':2}]}).encode()
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(origin+'/api/sale',data=data,headers=headers))
   self.assertEqual(e.exception.code,403);e.exception.close();headers['X-Shop-Token']=user['csrf']
   with urllib.request.urlopen(urllib.request.Request(origin+'/api/sale',data=data,headers=headers)) as r:first=json.load(r)
   with urllib.request.urlopen(urllib.request.Request(origin+'/api/sale',data=data,headers=headers)) as r:second=json.load(r)
   self.assertEqual(first,second);self.assertEqual(self.shop.state()['products'][0]['stock'],98)
  finally:server.shutdown();server.server_close()
