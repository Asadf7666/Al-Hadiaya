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
 def test_two_nodes_share_stock_without_function_restrictions(self):
  a=self.till('a');b=self.till('b',location='Outlet')
  self.sale(a,10);self.sale(b,5);self.sale(self.web.shop,5)
  a.sync();b.sync();a.sync()
  self.assertEqual(self.quantity(self.web.shop),0);self.assertEqual(self.quantity(a),0);self.assertEqual(self.quantity(b),0)
 def test_profiles_relay_between_tills_and_reversal(self):
  a=self.till('a');b=self.till('b')
  a.act('party',dict(name='Cafe customer',kind='customer',phone='9876543210',whatsapp_opt_in=True,whatsapp_consent_note='Customer explicitly requested receipt notifications'))
  bill=self.sale(a);a.sync();b.sync()
  self.assertEqual(b.state()['parties'][0]['name'],'Cafe customer')
  a.act('reverse',dict(id=bill,reason='Test cancellation'));a.sync();b.sync()
  self.assertEqual(self.quantity(self.web.shop),20);self.assertTrue(b.state()['documents'][0]['reversed'])
 def test_every_node_can_purchase_and_pay_supplier_dues_offline(self):
  a=self.till(location='Outlet');supplier=a.act('party',dict(kind='supplier',name='Offline supplier'))['id']
  a.act('purchase',dict(party_id=supplier,location='Warehouse',paid=0,items=[dict(product_id=self.pid,quantity=10,price=12)]))
  a.act('payment',dict(party_id=supplier,amount=50,method='UPI'))
  a.sync();a.sync();s=self.web.shop.state()
  self.assertEqual(self.quantity(self.web.shop),30)
  self.assertEqual(next(p['balance'] for p in s['parties'] if p['id']==supplier),7000)
  self.assertEqual(len(s['payments']),1)
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
  self.sale(self.web.shop,11);self.assertEqual(self.quantity(self.web.shop),9)
 def test_any_node_can_manage_recipes_and_consume_ingredients(self):
  milk=self.web.shop.act('product',dict(name='Milk',sku='MILK',category='Ingredients',unit='ml',kind='ingredient',price=0,cost=.1,stock=1000,location='Outlet'))['id']
  coffee=self.web.shop.act('product',dict(name='Coffee',sku='COFFEE',category='Coffee',unit='cup',kind='recipe',price=50,cost=0,stock=0,location='Outlet'))['id']
  self.web.shop.act('recipe',dict(product_id=coffee,items=[dict(ingredient_id=milk,quantity=150)]))
  a=self.till(location='Outlet');bill=a.act('sale',dict(location='Outlet',payment='Cash',items=[dict(product_id=coffee,quantity=1),dict(product_id=coffee,quantity=2)]))['id']
  with self.assertRaises(ValueError):self.sale(a,4,coffee,'Outlet')
  a.sync();self.assertEqual(self.quantity(self.web.shop,milk,'Outlet'),550)
  a.act('reverse',dict(id=bill,reason='Recipe reversal'));a.sync();self.assertEqual(self.quantity(self.web.shop,milk,'Outlet'),1000)
 def test_invalid_catalogue_event_rejected_and_stock_rolled_back(self):
  a=self.till();self.sale(a)
  with a.connect() as db:r=db.execute('SELECT * FROM sync_events ORDER BY date DESC LIMIT 1').fetchone();device=a.settings(db)['device_id'];business=a.settings(db)['cloud_business_id']
  event=dict(version=1,id=r['id'],date=r['date'],device=device,payload=json.loads(r['payload']))
  row=dict(a.state()['products'][0]);row.pop('stock');row['price']=-1;event['payload']['masters']['products']=[row]
  reply=self.web.hub.exchange(credential(a)['token'],dict(business_id=business,events=[event],cursor=0,protocol=5))
  self.assertTrue(reply['errors']);self.assertEqual(self.quantity(self.web.shop),20)

 def test_catalogue_settings_recipes_transfers_and_adjustments_from_cafe_node(self):
  a=self.till('cafe',location='Outlet');b=self.till('other')
  milk=a.act('product',dict(name='Milk',sku='MILK',category='Ingredients',unit='ml',kind='ingredient',cost=.1,stock=1000,location='Warehouse'))['id']
  coffee=a.act('product',dict(name='Coffee',sku='COFFEE',category='Coffee',unit='cup',kind='recipe',price=50))['id']
  a.act('recipe',dict(product_id=coffee,items=[dict(ingredient_id=milk,quantity=150)]))
  a.act('transfer',dict(product_id=milk,source='Warehouse',target='Outlet',quantity=500))
  a.act('adjust',dict(product_id=milk,location='Outlet',quantity=-10,note='Spillage'))
  a.act('settings',dict(name='Updated at cafe'))
  a.sync();a.sync();b.sync();b.sync()
  self.assertEqual(self.quantity(b,milk,'Outlet'),490)
  self.assertEqual(b.state()['settings']['name'],'Updated at cafe')
  self.assertEqual(b.state()['recipes'][0]['product_id'],coffee)
 def test_credit_sales_and_receipts_from_any_node(self):
  a=self.till('cafe',location='Outlet');customer=a.act('party',dict(kind='customer',name='Credit customer',credit_limit=500))['id']
  a.act('sale',dict(location='Warehouse',party_id=customer,paid=0,items=[dict(product_id=self.pid,quantity=2)]))
  a.act('payment',dict(party_id=customer,amount=10,method='Cash'))
  a.sync();self.assertEqual(next(p['balance'] for p in self.web.shop.state()['parties'] if p['id']==customer),3000)
 def test_competing_stock_leaves_local_bill_pending_without_negative_server_stock(self):
  a=self.till('a');b=self.till('b')
  self.sale(a,15);self.sale(b,10);a.sync();r=b.sync()
  self.assertGreater(r['pending'],0);self.assertEqual(self.quantity(self.web.shop),5)
  self.assertEqual(len(b.state()['documents']),1);self.assertTrue(b.state()['sync_errors'])
 def test_concurrent_payments_cannot_silently_overpay_or_drop_later_operations(self):
  customer=self.web.shop.act('party',dict(kind='customer',name='Customer'))['id']
  self.web.shop.act('sale',dict(location='Warehouse',party_id=customer,paid=0,items=[dict(product_id=self.pid,quantity=5)]))
  a=self.till('a');b=self.till('b')
  for shop in (a,b):shop.act('payment',dict(party_id=customer,amount=80,method='UPI'))
  b.act('expense',dict(name='Later event must wait',amount=10,method='Cash'))
  a.sync();r=b.sync();self.assertGreater(r['pending'],0)
  self.assertEqual(next(p['balance'] for p in self.web.shop.state()['parties'] if p['id']==customer),2000)
  self.assertFalse(self.web.shop.state()['expenses']);self.assertEqual(len(b.state()['payments']),1)
 def test_reversal_of_other_nodes_invoice_and_duplicate_reversal_conflict(self):
  a=self.till('a');b=self.till('b');bill=self.sale(a,2);a.sync();b.sync()
  b.act('reverse',dict(id=bill,reason='Other node reversal'));a.act('reverse',dict(id=bill,reason='Concurrent reversal'))
  b.sync();r=a.sync();self.assertTrue(r['pending']);self.assertEqual(self.quantity(self.web.shop),20)
 def test_existing_pair_can_change_origin_without_resetting_records(self):
  a=self.till();bill=self.sale(a)
  a.act('cloud_address',dict(url=self.url));self.assertEqual(a.state()['documents'][0]['id'],bill)
  a.sync();self.assertEqual(len(self.web.shop.state()['documents']),1)
 def test_upgrade_preserves_legacy_paired_identity_records_and_unsent_invoice(self):
  a=self.till();bill=self.sale(a,2)
  original=credential(a)
  with a.connect() as db:
   s=a.settings(db);ident=s['device_id']
   db.execute("DELETE FROM settings WHERE key='node_mode'")
   db.execute("UPDATE settings SET value=? WHERE key='admin_device_id'",(json.dumps('0123456789abcdef'),))
   event=db.execute('SELECT id,payload FROM sync_events ORDER BY date DESC LIMIT 1').fetchone();payload=json.loads(event['payload'])
   payload['deltas']['allocations']=[dict(device_id=ident,product_id=self.pid,location='Warehouse',delta=-2)]
   db.execute('UPDATE sync_events SET payload=? WHERE id=?',(json.dumps(payload),event['id']))
  updated=Shop(a.folder)
  self.assertEqual(updated.state()['settings']['device_id'],ident)
  self.assertEqual(credential(updated),original)
  updated.act('party',dict(kind='supplier',name='Supplier after upgrade'))
  updated.sync();self.assertEqual(self.quantity(self.web.shop),18)
  self.assertEqual(updated.state()['documents'][0]['id'],bill)
