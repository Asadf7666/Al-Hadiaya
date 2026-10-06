import datetime as dt,io,json,tempfile,unittest
from unittest.mock import patch
from app import Shop
from media_catalogue import public_state
from whatsapp_policy import sender_ready,message_allowed

class PolicyTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.shop=Shop(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def configured(self):
  self.shop.act('settings',{'phone':'9876543210'})
  self.shop.act('whatsapp_settings',{'whatsapp_enabled':True,'whatsapp_phone_id':'123','whatsapp_waba_id':'456','whatsapp_api_version':'v26.0'})
  return self.shop.state()['settings']
 def response(self,data):return io.BytesIO(json.dumps(data).encode())
 def test_rejected_account_pauses_sender_even_with_green_number(self):
  s=self.configured()
  with patch('whatsapp_policy.urllib.request.urlopen',side_effect=[self.response({'account_review_status':'REJECTED'}),self.response({'data':[{'id':'123','quality_rating':'GREEN'}]})]):
   self.assertFalse(sender_ready(self.shop,s,'test-credential')[0])
  self.assertFalse(self.shop.state()['settings']['whatsapp_enabled'])
 def test_approved_check_is_cached_but_new_credential_requires_revalidation(self):
  s=self.configured()
  with patch('whatsapp_policy.urllib.request.urlopen',side_effect=[self.response({'account_review_status':'APPROVED'}),self.response({'data':[{'id':'123','quality_rating':'GREEN'}]})]) as read:
   self.assertTrue(sender_ready(self.shop,s,'test-token-one')[0]);self.assertTrue(sender_ready(self.shop,s,'test-token-one')[0]);self.assertEqual(read.call_count,2)
  with patch('whatsapp_policy.urllib.request.urlopen',side_effect=OSError('No network')) as read:
   self.assertFalse(sender_ready(self.shop,s,'test-token-two')[0]);self.assertFalse(sender_ready(self.shop,s,'test-token-two')[0]);self.assertEqual(read.call_count,1)
 def test_unverified_template_cannot_reach_provider(self):
  from notifications import process_outbox
  self.configured();self.shop.act('whatsapp_settings',{'whatsapp_enabled':True,'whatsapp_daily_time':'00:00','whatsapp_internal_template':'not_checked'})
  self.shop.act('internal_contact',{'name':'Staff','phone':'9876543210','opt_in':True});self.shop.daily_update()
  with patch('whatsapp_policy.sender_ready',return_value=(True,'')),patch('notifications.read_token',return_value='test-token'),patch('notifications.deliver') as send:
   process_outbox(self.shop);send.assert_not_called()
  self.assertEqual(self.shop.state()['notifications'][0]['status'],'blocked')
 def test_phone_number_alone_does_not_grant_consent(self):
  with self.assertRaisesRegex(ValueError,'consent'):self.shop.act('party',{'name':'Buyer','kind':'customer','phone':'9876543210','whatsapp_marketing_opt_in':True})
  self.assertEqual(self.shop.state()['parties'],[])
 def test_sender_number_from_another_account_cannot_pass_validation(self):
  s=self.configured()
  with patch('whatsapp_policy.urllib.request.urlopen',side_effect=[self.response({'account_review_status':'APPROVED'}),self.response({'data':[{'id':'999','quality_rating':'GREEN'}]})]):
   self.assertFalse(sender_ready(self.shop,s,'test-token')[0])
 def test_sensitive_identifiers_blocked_but_barcode_and_order_allowed(self):
  with self.assertRaises(ValueError):message_allowed({'parameters':json.dumps(['Bank account: 123456789012'])})
  message_allowed({'parameters':json.dumps(['Barcode 8901234567890; order WA-1234'])})
 def test_catalogue_requires_review_and_product_change_removes_publication(self):
  from test_media_catalogue import png
  import base64
  pid=self.shop.act('product',{'name':'Cola','sku':'COLA','category':'Cold drinks','kind':'stock','unit':'bottle','price':50,'stock':5})['id']
  asset=self.shop.act('media_upload',{'name':'photo.png','content':base64.b64encode(png()).decode()})['id']
  data={'product_id':pid,'asset_id':asset,'published':True}
  with self.assertRaisesRegex(ValueError,'Confirm'):self.shop.act('catalogue_product',data)
  self.shop.act('catalogue_product',{**data,'policy_confirmed':True});self.shop.act('catalogue_settings',{'enabled':True})
  self.assertEqual(len(public_state(self.shop)['products']),1)
  with self.shop.connect() as db:db.execute("UPDATE products SET name='Vodka' WHERE id=?",(pid,))
  self.assertEqual(public_state(self.shop)['products'],[])
  with self.assertRaisesRegex(ValueError,'regulated'):self.shop.act('catalogue_product',{**data,'policy_confirmed':True})
