import datetime as dt,hashlib,hmac,json,tempfile,unittest
from unittest.mock import patch
from app import Shop
from outreach import receive,save_webhook
from notifications import process_outbox
from whatsapp_orders import act,feed
class WhatsAppOrderTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.shop=Shop(self.tmp.name)
  self.shop.act('whatsapp_settings',{'whatsapp_enabled':True,'whatsapp_phone_id':'123456','whatsapp_waba_id':'654321','whatsapp_api_version':'v26.0','whatsapp_language':'en_US','whatsapp_internal_template':'staff','token':'test-only-not-real'})
  self.pid=self.shop.act('product',{'name':'Cold drink','sku':'DRINK','category':'Cold drinks','kind':'stock','unit':'bottle','price':50,'wholesale_price':45,'cost':20,'stock':100,'minimum':0,'location':'Warehouse'})['id']
  act(self.shop,'commerce_product',{'catalog_id':'999','retailer_id':'CASE24','product_id':self.pid,'units':24,'active':True})
  with self.shop.connect() as db:
   for k,v in {'whatsapp_catalogue_id':'999','whatsapp_commerce_enabled':True,'whatsapp_catalogue_checked':dt.datetime.now(dt.timezone.utc).isoformat()}.items():db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(v),k))
  save_webhook(self.tmp.name,{'app_secret':'test-app-secret-value','verify_token':'verification-token-test'})
 def tearDown(self):self.tmp.cleanup()
 def incoming(self,mid='cart.1',body=None,phone='919876543210',kind='order',stamp=None):
  message={'id':mid,'from':phone,'timestamp':str(stamp or int(dt.datetime.now(dt.timezone.utc).timestamp())),'type':kind}
  if kind=='order':message['order']=body or {'catalog_id':'999','product_items':[{'product_retailer_id':'CASE24','quantity':'2','item_price':'1200','currency':'INR'}]}
  else:message['text']={'body':body or 'MENU'}
  value={'metadata':{'phone_number_id':'123456'},'contacts':[{'wa_id':phone,'profile':{'name':'Trader buyer'}}],'messages':[message]}
  raw=json.dumps({'object':'whatsapp_business_account','entry':[{'id':'654321','changes':[{'field':'messages','value':value}]}]}).encode()
  signature='sha256='+hmac.new(b'test-app-secret-value',raw,hashlib.sha256).hexdigest();return receive(self.shop,raw,signature)
 def order(self):return self.shop.state()['trade_orders'][0]
 def test_signed_cart_is_idempotent_pack_aware_and_does_not_change_accounts(self):
  before=self.shop.state();self.incoming();self.incoming();after=self.shop.state();o=self.order()
  self.assertEqual(len(after['trade_orders']),1);self.assertEqual(o['status'],'new');self.assertEqual(o['total'],240000);self.assertEqual(json.loads(o['items'])[0]['quantity'],48)
  for key in ['stocks','documents','payments','parties']:self.assertEqual(before[key],after[key])
  self.assertEqual(len([n for n in after['notifications'] if n['kind']=='order']),1)
 def test_unknown_sku_foreign_currency_and_price_differences_require_review(self):
  for n,item in enumerate([{'product_retailer_id':'UNKNOWN','quantity':1,'item_price':'1','currency':'INR'},{'product_retailer_id':'CASE24','quantity':1,'item_price':'1200','currency':'USD'},{'product_retailer_id':'CASE24','quantity':1,'item_price':'1','currency':'INR'}]):
   self.incoming('cart.'+str(n),{'catalog_id':'999','product_items':[item]});o=self.order();self.assertEqual(o['status'],'needs_review')
   with self.assertRaises(ValueError):act(self.shop,'trade_order_status',{'id':o['id'],'status':'confirmed'})
 def test_price_override_requires_customer_confirmation_and_stock_still_checked(self):
  self.incoming(body={'catalog_id':'999','product_items':[{'product_retailer_id':'CASE24','quantity':1,'item_price':'1','currency':'INR'}]});o=self.order()
  act(self.shop,'trade_order_status',{'id':o['id'],'status':'confirmed','customer_confirmed_price':True});self.assertEqual(self.order()['status'],'confirmed')
  self.shop.act('adjust',{'product_id':self.pid,'quantity':-100,'location':'Warehouse','note':'Test zero stock'})
  with self.assertRaises(ValueError):self.bill()
  self.assertEqual(self.shop.state()['documents'],[])
 def bill(self):
  o=self.order();items=json.loads(o['items']);return self.shop.act('sale',{'trade_order_id':o['id'],'items':[{'product_id':i['product_id'],'quantity':i['quantity']} for i in items],'price_tier':items[0]['tier'],'location':'Warehouse','payment':'Cash'})
 def test_lifecycle_atomic_invoice_and_duplicate_invoice_protection(self):
  self.incoming();o=self.order()
  with self.assertRaises(ValueError):self.bill()
  for status in ['confirmed','packing','ready']:act(self.shop,'trade_order_status',{'id':o['id'],'status':status})
  doc=self.bill();self.assertEqual(self.order()['invoice_id'],doc['id']);self.assertEqual(self.shop.state()['products'][0]['stock'],52)
  with self.assertRaises(ValueError):self.bill()
  with self.assertRaises(ValueError):act(self.shop,'trade_order_status',{'id':o['id'],'status':'cancelled'})
  act(self.shop,'trade_order_status',{'id':o['id'],'status':'completed'});self.assertEqual(self.order()['status'],'completed')
 def test_catalogue_and_status_reply_are_native_messages_and_private_to_number(self):
  self.incoming('menu',kind='text');row=self.shop.state()['notifications'][0];p=json.loads(row['payload']);self.assertEqual(p['interactive']['type'],'catalog_message')
  self.incoming();self.incoming('status',body='STATUS',kind='text');self.assertTrue(any(self.order()['id'] in n['parameters'] for n in self.shop.state()['notifications']))
  self.incoming('other-status',body='STATUS',phone='919876543211',kind='text');rows=[n for n in self.shop.state()['notifications'] if n['phone']=='919876543211'];self.assertNotIn(self.order()['id'],rows[0]['payload'])
 def test_stop_cancels_replies_and_order_contact_without_marketing_enrolment(self):
  self.incoming();self.incoming('stop',body='STOP',kind='text');self.assertEqual(self.order()['contact_allowed'],0)
  self.assertTrue(all(n['status']=='cancelled' for n in self.shop.state()['notifications']));self.assertEqual(self.shop.state()['parties'],[])
 def test_internal_alert_uses_service_window_then_blocks_pending_template(self):
  self.shop.act('internal_contact',{'name':'Staff','phone':'9876543211','opt_in':True});cid=self.shop.state()['internal_contacts'][0]['id']
  self.incoming('staff-start',body='Hello',phone='919876543211',kind='text');self.incoming()
  with patch('notifications.deliver',return_value=('accepted','OK','wamid.test')) as send:process_outbox(self.shop)
  sent=[c.args[2] for c in send.call_args_list if c.args[2]['internal_id']==cid];self.assertEqual(sent[0]['message_type'],'session');self.assertIn('WhatsApp order',sent[0]['payload'])
  with self.shop.connect() as db:
   db.execute('UPDATE whatsapp_sessions SET last_message=0 WHERE phone=?',('919876543211',))
   db.execute('INSERT INTO whatsapp_templates(name,language,status,category,body,supported,checked) VALUES(?,?,?,?,?,?,?)',('staff','en_US','PENDING','UTILITY','{{1}} {{2}} {{3}}',1,dt.datetime.now(dt.timezone.utc).isoformat()))
  act(self.shop,'trade_order_status',{'id':self.order()['id'],'status':'confirmed'})
  with patch('notifications.deliver',return_value=('accepted','OK','wamid.second')) as send:process_outbox(self.shop)
  self.assertTrue(any(n['internal_id']==cid and n['status']=='blocked' for n in self.shop.state()['notifications']))
  self.assertFalse(any(c.args[2]['internal_id']==cid for c in send.call_args_list))
 def test_whatsapp_order_syncs_and_can_be_billed_from_peer(self):
  self.incoming()
  with tempfile.TemporaryDirectory() as folder:
   peer=Shop(folder)
   with self.shop.connect() as db:events=[dict(r) for r in db.execute('SELECT * FROM sync_events ORDER BY rowid')]
   for e in events:
    e['payload']=json.loads(e['payload'])
    with peer.connect() as db:peer.apply_event(db,e)
   o=peer.state()['trade_orders'][0];act(peer,'trade_order_status',{'id':o['id'],'status':'confirmed'})
   result=peer.act('sale',{'trade_order_id':o['id'],'items':[{'product_id':self.pid,'quantity':48}],'location':'Warehouse','payment':'Cash'})
   with peer.connect() as db:e=dict(db.execute('SELECT * FROM sync_events ORDER BY rowid DESC LIMIT 1').fetchone())
   e['payload']=json.loads(e['payload'])
   with self.shop.connect() as db:self.shop.apply_event(db,e)
   self.assertEqual(self.order()['invoice_id'],result['id'])
 def test_concurrent_offline_invoices_raise_a_sync_conflict_and_roll_back(self):
  self.incoming()
  with self.shop.connect() as db:initial=[dict(r) for r in db.execute('SELECT * FROM sync_events ORDER BY rowid')]
  def apply(target,e):
   event={**e,'payload':json.loads(e['payload']) if isinstance(e['payload'],str) else e['payload']}
   with target.connect() as db:target.apply_event(db,event)
  with tempfile.TemporaryDirectory() as af,tempfile.TemporaryDirectory() as bf:
   a,b=Shop(af),Shop(bf)
   for peer in (a,b):
    for e in initial:apply(peer,e)
    act(peer,'trade_order_status',{'id':self.order()['id'],'status':'confirmed'})
    peer.act('sale',{'trade_order_id':self.order()['id'],'items':[{'product_id':self.pid,'quantity':48}],'location':'Warehouse','payment':'Cash'})
   with a.connect() as db:events=[dict(r) for r in db.execute('SELECT * FROM sync_events ORDER BY rowid')]
   for e in events:apply(self.shop,e)
   before=self.shop.state()
   with b.connect() as db:event=dict(db.execute('SELECT * FROM sync_events ORDER BY rowid DESC LIMIT 1').fetchone())
   with self.assertRaises(ValueError):apply(self.shop,event)
   after=self.shop.state();self.assertEqual(before['documents'],after['documents']);self.assertEqual(before['stocks'],after['stocks'])
 def test_catalogue_enable_requires_real_link_check_and_permission_errors_are_safe(self):
  with self.assertRaises(ValueError):act(self.shop,'commerce_settings',{'catalog_id':'777','enabled':True})
  with patch('whatsapp_orders.api',return_value={'data':[]}):
   with self.assertRaises(ValueError):act(self.shop,'commerce_check',{})
  with patch('whatsapp_orders.api',side_effect=[{'data':[{'id':'999'}]},{}]) as request:
   self.assertTrue(act(self.shop,'commerce_check',{})['linked']);self.assertTrue(request.call_args.args[2]['is_cart_enabled'])
 def test_meta_feed_has_case_price_photo_and_warehouse_availability(self):
  import base64,csv,io
  from test_media_catalogue import png
  from media_catalogue import upload
  image=upload(self.shop,{'name':'Product.png','content':base64.b64encode(png()).decode()})['id']
  self.shop.act('catalogue_product',{'product_id':self.pid,'asset_id':image,'published':True})
  self.shop.act('catalogue_settings',{'enabled':True})
  rows=list(csv.DictReader(io.StringIO(feed(self.shop,'https://example.com'))))
  self.assertEqual(rows[0]['id'],'CASE24');self.assertEqual(rows[0]['price'],'1200.00 INR');self.assertEqual(rows[0]['availability'],'in stock');self.assertEqual(rows[0]['image_link'],'https://example.com/media/'+image)
  self.shop.act('adjust',{'product_id':self.pid,'quantity':-100,'location':'Warehouse','note':'Empty stock test'})
  self.assertEqual(list(csv.DictReader(io.StringIO(feed(self.shop,'https://example.com'))))[0]['availability'],'out of stock')
 def test_protocol_three_node_is_rejected_without_losing_local_records(self):
  from cloud_sync import Hub
  with self.assertRaises(ValueError):Hub(self.shop).pair({'protocol':3})
  self.assertEqual(self.shop.state()['products'][0]['stock'],100)
 def test_forged_webhook_cannot_create_order(self):
  with self.assertRaises(PermissionError):receive(self.shop,b'{}','sha256=fake')
  self.assertEqual(self.shop.state()['trade_orders'],[])
if __name__=='__main__':unittest.main()
