import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Shop
from notifications import process_outbox,whatsapp_number

class NotificationTests(unittest.TestCase):
    def setUp(self):
        ready=patch('whatsapp_policy.sender_ready',return_value=(True,''));ready.start();self.addCleanup(ready.stop)
        self.tmp=tempfile.TemporaryDirectory()
        self.shop=Shop(Path(self.tmp.name))
        self.shop.act('whatsapp_settings',{'whatsapp_profiles':False,'whatsapp_catalogue':False,'whatsapp_stock':False,'whatsapp_recipes':False,'whatsapp_enabled':True,'whatsapp_phone_id':'123456','whatsapp_api_version':'v99.0','whatsapp_language':'en','whatsapp_internal_template':'internal_update','whatsapp_invoice_template':'invoice_update','whatsapp_low_stock':True,'whatsapp_transfers':True,'whatsapp_purchases':True,'whatsapp_daily_time':'00:00'})
        with self.shop.connect() as db:
            import datetime as dt
            for t in ('internal_update','invoice_update'):db.execute('INSERT INTO whatsapp_templates(name,language,status,category,body,supported,checked) VALUES(?,?,?,?,?,?,?)',(t,'en','APPROVED','UTILITY','{{1}} {{2}} {{3}}',1,dt.datetime.now(dt.timezone.utc).isoformat()))
        self.shop.act('internal_contact',{'name':'Owner','phone':'9876543210','opt_in':True})
    def tearDown(self):self.tmp.cleanup()
    def test_transfer_and_purchase_queue_internal_updates(self):
        pid=self.shop.act('product',{'name':'Drink','sku':'DR','category':'Cold drinks','kind':'stock','unit':'bottle','price':50,'cost':20,'stock':10,'minimum':0,'location':'Warehouse'})['id']
        self.shop.act('transfer',{'product_id':pid,'quantity':2,'source':'Warehouse','target':'Outlet'})
        supplier=self.shop.act('party',{'name':'Supplier','kind':'supplier'})['id']
        self.shop.act('purchase',{'party_id':supplier,'items':[{'product_id':pid,'quantity':2,'price':20}],'location':'Warehouse','payment':'Cash','reference':'SUP-1'})
        updates=[r for r in self.shop.state()['notifications'] if r['kind']=='internal']
        self.assertEqual(len(updates),2)
        self.assertTrue(any('Transfer' in r['parameters'] for r in updates))
        self.assertTrue(any('Purchase' in r['parameters'] for r in updates))

    def test_number_normalization(self):
        self.assertEqual(whatsapp_number('98765 43210'),'919876543210')
        self.assertEqual(whatsapp_number('+91 98765 43210'),'919876543210')
        with self.assertRaises(ValueError):whatsapp_number('123')
    def test_daily_summary_is_idempotent_and_internal_is_sent(self):
        self.shop.daily_update();self.shop.daily_update()
        self.assertEqual(len(self.shop.state()['notifications']),1)
        with patch('notifications.read_token',return_value='test-only'),patch('notifications.deliver',return_value=('accepted','API accepted','test-id')) as send:
            self.assertEqual(process_outbox(self.shop)['processed'],1)
            process_outbox(self.shop)
            self.assertEqual(send.call_count,1)
        self.assertEqual(self.shop.state()['notifications'][0]['status'],'accepted')
    def test_optout_cancels_already_queued_internal_message(self):
        self.shop.daily_update()
        contact=self.shop.state()['internal_contacts'][0]
        self.shop.act('internal_contact',{**contact,'opt_in':False})
        with patch('notifications.read_token',return_value='test-only'),patch('notifications.deliver') as send:
            process_outbox(self.shop);send.assert_not_called()
        self.assertEqual(self.shop.state()['notifications'][0]['status'],'cancelled')
    def test_uncertain_result_does_not_resend(self):
        self.shop.daily_update()
        with patch('notifications.read_token',return_value='test-only'),patch('notifications.deliver',return_value=('uncertain','Response lost','')) as send:
            process_outbox(self.shop);process_outbox(self.shop)
            self.assertEqual(send.call_count,1)
        self.assertEqual(self.shop.state()['notifications'][0]['status'],'uncertain')
    def test_missing_credential_leaves_queue_waiting(self):
        self.shop.daily_update()
        self.assertEqual(process_outbox(self.shop)['processed'],0)
        self.assertEqual(self.shop.state()['notifications'][0]['status'],'queued')
    def test_customer_invoice_only_with_consent_and_optout_before_send(self):
        pid=self.shop.act('product',{'name':'Drink','sku':'DR','category':'Cold drinks','kind':'stock','unit':'bottle','price':50,'cost':20,'stock':5,'minimum':0,'location':'Outlet'})['id']
        cid=self.shop.act('party',{'name':'Customer','kind':'customer','phone':'9876543211','whatsapp_opt_in':True,'whatsapp_consent_note':'Customer explicitly requested receipts during test checkout'})['id']
        self.shop.act('sale',{'items':[{'product_id':pid,'quantity':1}],'party_id':cid,'payment':'Cash','location':'Outlet'})
        invoices=[r for r in self.shop.state()['notifications'] if r['kind']=='invoice']
        self.assertEqual(len(invoices),1)
        self.shop.act('party',{'id':cid,'name':'Customer','kind':'customer','phone':'9876543211','whatsapp_opt_in':False})
        with patch('notifications.read_token',return_value='test-only'),patch('notifications.deliver') as send:
            process_outbox(self.shop);send.assert_not_called()
        self.assertEqual(self.shop.state()['notifications'][0]['status'],'cancelled')

if __name__=='__main__':unittest.main()
