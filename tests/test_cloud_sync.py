"""Exercise real HTTP pairing and event exchange with independent SQLite tills."""
import copy,json,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from app import Shop
from cloud.server import Online,Handler
from cloud_sync import credential,request

class ConnectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.web=Online(self.root/'server','http://127.0.0.1',False)
  self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.http.online=self.web
  self.url='http://127.0.0.1:'+str(self.http.server_port);self.web.origin=self.url
  self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
  self.pid=self.web.shop.act('product',dict(name='Drink',sku='DR',unit='bottle',kind='stock',category='Cold drinks',price=20,cost=10,stock=20,location='Warehouse'))['id']
 def tearDown(self):
  self.http.shutdown();self.http.server_close();self.thread.join();self.tmp.cleanup()
 def till(self,name='till',percentage=50,location='Warehouse',sample=False):
  shop=Shop(self.root/name)
  if sample:shop.act('demo',{})
  code=self.web.hub.code(location,percentage)['code']
  shop.act('cloud_pair',dict(url=self.url,code=code,name=name,replace_sample=sample))
  return shop
 def quantity(self,shop,pid=None,loc='Warehouse'):
  return next(r['quantity'] for r in shop.state()['stocks'] if r['product_id']==(pid or self.pid) and r['location']==loc)
 def sale(self,shop,count=1,pid=None,loc='Warehouse'):
  return shop.act('sale',dict(location=loc,payment='Cash',items=[dict(product_id=pid or self.pid,quantity=count)]))['id']
 def test_pair_replaces_samples_with_verified_backup_and_private_credential(self):
  till=self.till(sample=True);s=till.state()
  self.assertEqual(len(s['products']),1);self.assertEqual(self.quantity(till),20)
  self.assertTrue(list((till.folder/'backups').glob('*.sqlite3')))
  key=credential(till)['token'];self.assertNotIn(key,json.dumps(s))
  with till.connect() as db:self.assertNotIn(key,' '.join(r['value'] for r in db.execute('SELECT * FROM settings')))
  self.assertTrue(s['settings']['cloud_business_id'])
 def test_offline_bills_upload_once_and_online_changes_download(self):
  till=self.till();bill=self.sale(till,3)
  self.assertEqual(self.quantity(self.web.shop),20)
  with patch('cloud_sync.request',side_effect=ValueError('No network')):
   with self.assertRaises(ValueError):till.sync()
  self.assertEqual(len(till.state()['documents']),1)
  till.sync();till.sync();self.assertEqual(self.quantity(self.web.shop),17)
  self.assertEqual(len(self.web.shop.state()['documents']),1)
  self.web.shop.act('party',dict(name='Online customer',kind='customer',phone='9876543210'))
  till.sync();self.assertEqual(till.state()['parties'][0]['name'],'Online customer')
  self.assertEqual(till.state()['documents'][0]['id'],bill)
 def test_two_offline_pcs_and_online_pool_cannot_oversell(self):
  a=self.till('a',50);b=self.till('b',50)
  self.sale(a,10);self.sale(b,5);self.sale(self.web.shop,5)
  for shop in (a,b,self.web.shop):
   with self.assertRaises(ValueError):self.sale(shop)
  a.sync();b.sync();a.sync()
  self.assertEqual(self.quantity(self.web.shop),0);self.assertEqual(self.quantity(a),0);self.assertEqual(self.quantity(b),0)
 def test_profiles_relay_between_tills_and_reversal(self):
  a=self.till('a');b=self.till('b')
  a.act('party',dict(name='Cafe customer',kind='customer',phone='9876543210',whatsapp_opt_in=True))
  bill=self.sale(a);a.sync();b.sync()
  self.assertEqual(b.state()['parties'][0]['name'],'Cafe customer')
  a.act('reverse',dict(id=bill,reason='Test cancellation'));a.sync();b.sync()
  self.assertEqual(self.quantity(self.web.shop),20);self.assertTrue(b.state()['documents'][0]['reversed'])
 def test_unused_allowance_release_and_regrant(self):
  a=self.till();a.act('release_allocation',dict(product_id=self.pid,quantity=10));a.sync()
  self.sale(self.web.shop,20);a.sync();self.assertEqual(self.quantity(a),0)
 def test_retry_after_lost_upload_response_never_duplicates(self):
  a=self.till();self.sale(a,2)
  real=request
  def lost(*args,**kw):
   real(*args,**kw);raise ValueError('Response lost')
  with patch('cloud_sync.request',side_effect=lost):
   with self.assertRaises(ValueError):a.sync()
  a.sync();self.assertEqual(self.quantity(self.web.shop),18);self.assertEqual(len(self.web.shop.state()['documents']),1)
 def test_pairing_code_is_single_device_and_credentials_can_be_disabled(self):
  code=self.web.hub.code('Warehouse',50)['code'];a=Shop(self.root/'a');b=Shop(self.root/'b')
  a.act('cloud_pair',dict(url=self.url,code=code,name='A'))
  with self.assertRaises(ValueError):b.act('cloud_pair',dict(url=self.url,code=code,name='B'))
  with self.web.shop.connect() as db:db.execute('UPDATE cloud_peers SET active=0')
  with self.assertRaises(ValueError):a.sync()
  with self.assertRaises(ValueError):self.sale(self.web.shop,11)
 def test_recipe_consumes_reserved_ingredients(self):
  milk=self.web.shop.act('product',dict(name='Milk',sku='MILK',category='Ingredients',unit='ml',kind='ingredient',price=0,cost=.1,stock=1000,location='Outlet'))['id']
  coffee=self.web.shop.act('product',dict(name='Coffee',sku='COFFEE',category='Coffee',unit='cup',kind='recipe',price=50,cost=0,stock=0,location='Outlet'))['id']
  self.web.shop.act('recipe',dict(product_id=coffee,items=[dict(ingredient_id=milk,quantity=150)]))
  a=self.till(location='Outlet');self.sale(a,3,coffee,'Outlet')
  with self.assertRaises(ValueError):self.sale(a,1,coffee,'Outlet')
  a.sync();self.assertEqual(self.quantity(self.web.shop,milk,'Outlet'),550)
 def test_forged_catalogue_event_rejected_and_stock_rolled_back(self):
  a=self.till();self.sale(a)
  with a.connect() as db:r=db.execute('SELECT * FROM sync_events ORDER BY date DESC LIMIT 1').fetchone();device=a.settings(db)['device_id'];business=a.settings(db)['cloud_business_id']
  event=dict(version=1,id=r['id'],date=r['date'],device=device,payload=json.loads(r['payload']))
  event['payload']['masters']['products']=[dict(id=self.pid,name='Forged')]
  reply=self.web.hub.exchange(credential(a)['token'],dict(business_id=business,events=[event],cursor=0))
  self.assertTrue(reply['errors']);self.assertEqual(self.quantity(self.web.shop),20)
