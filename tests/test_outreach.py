import datetime as dt
import hashlib
import hmac
import json
import tempfile
import unittest
from unittest.mock import patch
from app import Shop
from notifications import process_outbox
from outreach import act,receive,save_webhook,challenge

class OutreachTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.shop=Shop(self.tmp.name)
  self.shop.act('whatsapp_settings',{'whatsapp_enabled':True,'whatsapp_phone_id':'123456','whatsapp_waba_id':'654321','whatsapp_api_version':'v26.0','whatsapp_language':'en_US'})
  with self.shop.connect() as db:
   db.execute('INSERT INTO whatsapp_templates VALUES(?,?,?,?,?,?,?)',('offers','en_US','APPROVED','MARKETING','Hello {{1}}, {{2}}: {{3}}',1,dt.datetime.now(dt.timezone.utc).isoformat()))
 def tearDown(self):self.tmp.cleanup()
 def customer(self,phone='9876543210',**kw):
  return self.shop.act('party',{'name':'Customer','kind':'customer','phone':phone,**kw})['id']
 def draft(self,ids,**kw):
  return act(self.shop,'campaign_create',dict(name='Weekend',offer='Coffee offer',template='offers',language='en_US',customer_ids=ids,**kw))['id']
 def approve(self,ident):
  with patch('outreach.read_token',return_value='test-only'):
   return act(self.shop,'campaign_approve',{'id':ident,'confirmed':True})
 def test_receipt_consent_does_not_authorize_marketing(self):
  cid=self.customer(whatsapp_opt_in=True)
  with self.assertRaises(ValueError):self.draft([cid])
 def test_approval_deduplicates_mobile_and_does_not_send_twice(self):
  a=self.customer(whatsapp_marketing_opt_in=True);b=self.customer('+91 98765 43210',whatsapp_marketing_opt_in=True)
  ident=self.draft([a,b]);self.assertEqual(self.shop.state()['notifications'],[])
  self.assertEqual(self.approve(ident)['queued'],1)
  with self.assertRaises(ValueError):self.approve(ident)
  with patch('notifications.read_token',return_value='test-only'),patch('notifications.deliver',return_value=('accepted','OK','wamid.1')) as send:
   process_outbox(self.shop);process_outbox(self.shop);self.assertEqual(send.call_count,1)
   self.assertEqual(send.call_args.args[2]['language'],'en_US')
 def test_optout_after_approval_and_cancel_before_processing(self):
  cid=self.customer(whatsapp_marketing_opt_in=True);ident=self.draft([cid]);self.approve(ident)
  self.shop.act('party',{'id':cid,'name':'Customer','kind':'customer','phone':'9876543210','whatsapp_marketing_opt_in':False})
  with patch('notifications.read_token',return_value='test-only'),patch('notifications.deliver') as send:
   process_outbox(self.shop);send.assert_not_called()
  self.assertEqual(self.shop.state()['notifications'][0]['status'],'cancelled')
 def test_schedule_is_not_processed_early_and_cancellation_is_final(self):
  cid=self.customer(whatsapp_marketing_opt_in=True)
  ident=self.draft([cid],scheduled=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=3)).isoformat());self.approve(ident)
  with patch('notifications.read_token',return_value='test-only'),patch('notifications.deliver') as send:
   self.assertEqual(process_outbox(self.shop)['processed'],0);send.assert_not_called()
  act(self.shop,'campaign_cancel',{'id':ident})
  self.assertEqual(self.shop.state()['notifications'][0]['status'],'cancelled')
 def webhook(self,value,signature=True):
  raw=json.dumps({'object':'whatsapp_business_account','entry':[{'id':'654321','changes':[{'field':'messages','value':{'metadata':{'phone_number_id':'123456'},**value}}]}]}).encode()
  sig='sha256='+hmac.new(b'test-app-secret-value',raw,hashlib.sha256).hexdigest() if signature else 'sha256=wrong'
  return receive(self.shop,raw,sig)
 def test_signed_statuses_and_stop_reply_are_idempotent(self):
  save_webhook(self.tmp.name,{'app_secret':'test-app-secret-value','verify_token':'verification-token-test'})
  cid=self.customer(whatsapp_opt_in=True,whatsapp_marketing_opt_in=True);ident=self.draft([cid]);self.approve(ident)
  with self.shop.connect() as db:db.execute("UPDATE notifications SET status='accepted',provider_id='wamid.1'")
  with self.assertRaises(PermissionError):self.webhook({'statuses':[{'id':'wamid.1','status':'read','timestamp':'1'}]},False)
  self.webhook({'statuses':[{'id':'wamid.1','status':'read','timestamp':'3'}]})
  self.webhook({'statuses':[{'id':'wamid.1','status':'sent','timestamp':'4'}]})
  self.assertEqual(self.shop.state()['notifications'][0]['status'],'read')
  self.webhook({'messages':[{'id':'stop.1','from':'919876543210','type':'text','text':{'body':'STOP'}}]})
  self.webhook({'messages':[{'id':'stop.1','from':'919876543210','type':'text','text':{'body':'STOP'}}]})
  customer=self.shop.state()['parties'][0]
  self.assertFalse(customer['whatsapp_opt_in']);self.assertFalse(customer['whatsapp_marketing_opt_in'])
  self.assertEqual(challenge(self.shop,{'hub.mode':['subscribe'],'hub.verify_token':['verification-token-test'],'hub.challenge':['123']}),'123')
 def test_optout_and_marketing_consent_sync_to_another_node(self):
  self.customer(whatsapp_marketing_opt_in=True)
  with tempfile.TemporaryDirectory() as other:
   peer=Shop(other)
   with self.shop.connect() as db:event=dict(db.execute('SELECT * FROM sync_events ORDER BY rowid DESC LIMIT 1').fetchone())
   event.update(version=1,payload=json.loads(event['payload']))
   with peer.connect() as db:peer.apply_event(db,event)
   self.assertTrue(peer.state()['parties'][0]['whatsapp_marketing_opt_in'])
 def test_hub_sender_queues_offline_customer_sale_once(self):
  from cloud_sync import Hub
  with tempfile.TemporaryDirectory() as folder:
   offline=Shop(folder)
   pid=offline.act('product',{'name':'Drink','sku':'DR','category':'Cold drinks','kind':'stock','unit':'bottle','price':50,'cost':20,'stock':5,'minimum':0,'location':'Outlet'})['id']
   cid=offline.act('party',{'name':'Buyer','kind':'customer','phone':'9876543211','whatsapp_opt_in':True})['id']
   offline.act('sale',{'items':[{'product_id':pid,'quantity':1}],'party_id':cid,'payment':'Cash','location':'Outlet'})
   with offline.connect() as db:events=[dict(r) for r in db.execute('SELECT * FROM sync_events ORDER BY rowid')]
   with self.shop.connect() as db:db.execute("UPDATE settings SET value=? WHERE key='whatsapp_invoice_template'",(json.dumps('receipt'),))
   for event in events:
    event.update(version=1,payload=json.loads(event['payload']))
    with self.shop.connect() as db:
     if self.shop.apply_event(db,event):self.shop.queue_synced_updates(db,event)
   self.assertEqual(len([n for n in self.shop.state()['notifications'] if n['kind']=='invoice']),1)
   with self.shop.connect() as db:
    self.shop.queue_synced_updates(db,event)
   self.assertEqual(len([n for n in self.shop.state()['notifications'] if n['kind']=='invoice']),1)
 def test_public_webhook_http_routes_require_signature(self):
  from cloud.server import Handler,Online
  from http.server import ThreadingHTTPServer
  import threading,urllib.request,urllib.error
  online=Online(self.tmp.name,'http://localhost',False)
  save_webhook(self.tmp.name,{'app_secret':'test-app-secret-value','verify_token':'verification-token-test'})
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.online=online
  threading.Thread(target=server.serve_forever,daemon=True).start()
  origin='http://127.0.0.1:'+str(server.server_port)
  try:
   with urllib.request.urlopen(origin+'/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verification-token-test&hub.challenge=123') as response:self.assertEqual(response.read(),b'123')
   with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(urllib.request.Request(origin+'/webhooks/whatsapp',data=b'{}',headers={'X-Hub-Signature-256':'sha256=wrong'}))
   self.assertEqual(exc.exception.code,403)
   for path in ('/privacy','/data-deletion'):
    with urllib.request.urlopen(origin+path) as response:self.assertEqual(response.status,200)
  finally:server.shutdown();server.server_close()
 def test_campaign_management_is_owner_only_online(self):
  from cloud.server import Online
  with tempfile.TemporaryDirectory() as folder:
   online=Online(folder,'http://localhost',False)
   for role in ('manager','cashier','viewer'):
    with self.assertRaises(PermissionError):online.act({'role':role},'campaign_create',{})

if __name__=='__main__':unittest.main()
