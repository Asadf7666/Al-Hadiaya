import base64,datetime as dt,json,secrets,struct,tempfile,unittest,zlib
from unittest.mock import patch
from app import Shop,restore_backup
from media_catalogue import upload,public_state,public_asset,order,asset_path
from notifications import deliver
from outreach import act

def png():
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\xcc\x88'))+chunk(b'IEND',b'')
class MediaCatalogueTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.shop=Shop(self.tmp.name)
  self.asset=upload(self.shop,{'name':'Photo.png','content':base64.b64encode(png()).decode()})['id']
  self.pid=self.shop.act('product',{'name':'Test drink','sku':'TEST','category':'Cold drinks','kind':'stock','unit':'bottle','price':50,'cost':20,'stock':5,'minimum':0,'location':'Warehouse'})['id']
 def tearDown(self):self.tmp.cleanup()
 def publish(self):
  self.shop.act('catalogue_product',{'product_id':self.pid,'asset_id':self.asset,'published':True,'policy_confirmed':True})
  self.shop.act('catalogue_settings',{'enabled':True,'banner':self.asset})
 def request(self,**kw):return dict(request_key=secrets.token_hex(16),name='Buyer',phone='9876543210',contact_consent=True,items=[{'id':self.pid,'quantity':2,'price':1}],**kw)
 def test_upload_validation_content_addressing_and_traversal(self):
  self.assertEqual(upload(self.shop,{'name':'Other.png','content':base64.b64encode(png()).decode()})['id'],self.asset)
  for raw in [b'<svg/>',b'bad',b'\xff\xd8\xff'*10,b'X'*5000001]:
   with self.assertRaises(ValueError):upload(self.shop,{'content':base64.b64encode(raw).decode()})
  with self.assertRaises(ValueError):asset_path(self.shop,'../../shop.sqlite3')
 def test_only_published_priced_sellable_items_and_public_images(self):
  self.assertEqual(public_state(self.shop)['products'],[]);self.assertFalse(public_asset(self.shop,self.asset))
  self.publish();p=public_state(self.shop)['products'][0];self.assertNotIn('cost',p);self.assertNotIn('stock',p);self.assertTrue(public_asset(self.shop,self.asset))
  with self.shop.connect() as db:db.execute('UPDATE products SET price=0 WHERE id=?',(self.pid,))
  self.assertEqual(public_state(self.shop)['products'],[])
  with self.assertRaises(ValueError):self.shop.act('catalogue_product',{'product_id':self.pid,'asset_id':self.asset,'published':True,'policy_confirmed':True})
 def test_request_reprices_is_idempotent_and_leaves_ledgers_unchanged(self):
  self.publish();before=self.shop.state();data=self.request();one=order(self.shop,data);two=order(self.shop,data)
  self.assertEqual(one['id'],two['id']);self.assertEqual(one['total'],10000)
  after=self.shop.state();self.assertEqual(len(after['catalogue_orders']),1)
  for key in ['stocks','documents','payments','parties']:self.assertEqual(before[key],after[key])
  with self.assertRaises(ValueError):order(self.shop,{**self.request(),'contact_consent':False})
  with self.assertRaises(ValueError):order(self.shop,{**self.request(),'items':[{'id':self.pid,'quantity':101}]})
  self.shop.act('catalogue_settings',{'enabled':False})
  with self.assertRaises(ValueError):order(self.shop,self.request())
 def test_concurrent_duplicate_requests_create_one_record(self):
  from concurrent.futures import ThreadPoolExecutor
  self.publish();data=self.request()
  with ThreadPoolExecutor(max_workers=4) as pool:ids=list(pool.map(lambda _:order(self.shop,data)['id'],range(4)))
  self.assertEqual(len(set(ids)),1);self.assertEqual(len(self.shop.state()['catalogue_orders']),1)
 def test_image_approval_and_provider_payload_have_image_header(self):
  self.shop.act('whatsapp_settings',{'whatsapp_enabled':True,'whatsapp_phone_id':'123456','whatsapp_api_version':'v26.0','whatsapp_language':'en_US'})
  cid=self.shop.act('party',{'name':'Buyer','kind':'customer','phone':'9876543210','whatsapp_marketing_opt_in':True,'whatsapp_consent_note':'Customer explicitly requested offers during test signup'})['id']
  with self.shop.connect() as db:
   db.execute('INSERT INTO whatsapp_templates(name,language,status,category,body,supported,checked,header_format,parameter_count) VALUES(?,?,?,?,?,?,?,?,?)',('photo','en_US','APPROVED','MARKETING','Hello {{1}}, {{2}}: {{3}}',1,dt.datetime.now(dt.timezone.utc).isoformat(),'IMAGE',3))
  data=dict(name='Image campaign',offer='Fresh drinks',template='photo',language='en_US',customer_ids=[cid])
  with self.assertRaises(ValueError):act(self.shop,'campaign_create',data)
  ident=act(self.shop,'campaign_create',{**data,'asset_id':self.asset})['id']
  with patch('outreach.read_token',return_value='test'),patch('media_catalogue.meta_image',return_value='media.1'):
   self.assertEqual(act(self.shop,'campaign_approve',{'id':ident,'confirmed':True})['queued'],1)
  row=self.shop.state()['notifications'][0]
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return b'{"messages":[{"id":"wamid.test"}]}'
  with patch('notifications.urllib.request.urlopen',return_value=Response()) as send:
   self.assertEqual(deliver(self.shop.state()['settings'],'test',row)[0],'accepted')
   payload=json.loads(send.call_args.args[0].data);components=payload['template']['components']
   self.assertEqual(components[0]['parameters'][0]['image']['id'],'media.1');self.assertEqual(len(components[1]['parameters']),3)
 def test_backup_sidecar_restores_images(self):
  backup=self.shop.backup()['paths'][0]
  with tempfile.TemporaryDirectory() as folder:
   target=Shop(folder);restore_backup(target,backup)
   self.assertEqual(asset_path(target,self.asset).read_bytes(),png())
 def test_public_http_images_require_publication_and_origin_for_orders(self):
  from cloud.server import Handler,Online
  from http.server import ThreadingHTTPServer
  import threading,urllib.request,urllib.error
  online=Online(self.tmp.name,'http://localhost',False);server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.online=online
  threading.Thread(target=server.serve_forever,daemon=True).start();origin='http://127.0.0.1:'+str(server.server_port);online.origin=origin
  try:
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(origin+'/media/'+self.asset)
   self.assertEqual(e.exception.code,404);self.publish()
   with urllib.request.urlopen(origin+'/media/'+self.asset) as r:self.assertEqual(r.read(),png())
   data=json.dumps(self.request()).encode()
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(origin+'/api/catalogue-order',data=data,headers={'Origin':'http://wrong'}))
   self.assertEqual(e.exception.code,403)
   with urllib.request.urlopen(urllib.request.Request(origin+'/api/catalogue-order',data=data,headers={'Origin':origin,'Content-Type':'application/json'})) as r:self.assertEqual(json.load(r)['total'],10000)
  finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
