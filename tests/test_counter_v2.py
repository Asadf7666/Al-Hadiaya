import json,tempfile,unittest
from app import Shop

class CounterTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.shop=Shop(self.tmp.name)
        self.pid=self.shop.act('product',{'name':'Juice','sku':'J1','category':'Juices','unit':'pack','price':30,'cost':20,'location':'Warehouse'})['id']
        self.supplier=self.shop.act('party',{'name':'Distributor','kind':'supplier'})['id']
        self.customer=self.shop.act('party',{'name':'Hotel Sagar','kind':'customer'})['id']
        self.purchase=self.shop.act('purchase',{'party_id':self.supplier,'location':'Warehouse','paid':0,'items':[{'product_id':self.pid,'quantity':20,'price':20,'lot':'B1','expiry':'2099-01-31'}]})['id']
    def tearDown(self):self.tmp.cleanup()
    def doc(self,ident):
        with self.shop.connect() as db:
            row=dict(db.execute('SELECT * FROM documents WHERE id=?',(ident,)).fetchone());row['snapshot']=json.loads(row['snapshot']);return row
    def balance(self,party):
        with self.shop.connect() as db:return db.execute('SELECT balance FROM parties WHERE id=?',(party,)).fetchone()[0]
    def stock(self):
        with self.shop.connect() as db:return db.execute("SELECT quantity FROM stocks WHERE product_id=? AND location='Warehouse'",(self.pid,)).fetchone()[0]
    def lot(self):
        with self.shop.connect() as db:return db.execute("SELECT quantity FROM lots WHERE product_id=? AND lot='B1'",(self.pid,)).fetchone()[0]
    def sale(self,quantity=10,**extra):
        return self.shop.act('sale',{'location':'Warehouse','items':[{'product_id':self.pid,'quantity':quantity}],**extra})['id']

    def test_partial_return_issues_a_credit_note_and_restocks_the_same_lot(self):
        sale=self.sale(10,party_id=self.customer,paid=100)
        self.assertEqual((self.balance(self.customer),self.stock(),self.lot()),(20000,10,10))
        note=self.shop.act('return',{'id':sale,'reason':'Leaking packs','items':[{'line':0,'quantity':4}]})
        self.assertEqual((note['credit'],note['refund']),(12000,0),'What is still owed is cancelled before any money goes back.')
        saved=self.doc(note['id'])
        self.assertEqual((saved['kind'],saved['reference'],saved['total'],saved['paid']),('sale_return',sale,12000,0))
        self.assertRegex(note['id'],r'^AH[0-9A-F]{6}C\d{7}$')
        self.assertEqual((self.balance(self.customer),self.stock(),self.lot()),(8000,14,14))
        with self.assertRaisesRegex(ValueError,'Only 6 pack'):self.shop.act('return',{'id':sale,'reason':'x','items':[{'line':0,'quantity':7}]})
        second=self.shop.act('return',{'id':sale,'reason':'Damaged, not for resale','restock':False,'items':[{'line':0,'quantity':6}]})
        self.assertEqual((second['credit'],second['refund']),(8000,10000));self.assertEqual((self.balance(self.customer),self.stock()),(0,14))
        with self.assertRaisesRegex(ValueError,'left to return'):self.shop.act('return',{'id':sale,'reason':'x','items':[{'line':0,'quantity':1}]})
        with self.assertRaisesRegex(ValueError,'already returned'):self.shop.act('reverse',{'id':sale,'reason':'x'})
        with self.assertRaisesRegex(ValueError,'cannot be reversed'):self.shop.act('reverse',{'id':note['id'],'reason':'x'})

    def test_walk_in_return_refunds_in_full_and_tax_parts_still_add_up(self):
        self.shop.act('settings',{'name':'Al Hadiya Traders','invoice_prefix':'AH','state':'29','gstin':'29ABCDE1234F1Z5','gst_enabled':True})
        self.shop.act('product',{'id':self.pid,'name':'Juice','sku':'J1','category':'Juices','unit':'pack','price':30,'cost':20,'gst':5,'hsn':'2202','tax_verified':True})
        sale=self.sale(7);note=self.shop.act('return',{'id':sale,'reason':'Changed mind','payment':'UPI','items':[{'line':0,'quantity':3}]})
        self.assertEqual((note['refund'],note['credit'],note['method']),(9000,0,'UPI'))
        item=self.doc(note['id'])['snapshot']['items'][0]
        self.assertEqual(item['taxable']+item['tax'],item['total']);self.assertEqual(item['cgst_amount']+item['sgst_amount']+item['cess_amount'],item['tax'])
        with self.assertRaisesRegex(ValueError,'Refund at least'):self.shop.act('return',{'id':sale,'reason':'x','refund':0,'items':[{'line':0,'quantity':1}]})

    def test_purchase_return_issues_a_debit_note_and_removes_stock(self):
        note=self.shop.act('return',{'id':self.purchase,'reason':'Short dated','items':[{'line':0,'quantity':5}]})
        saved=self.doc(note['id']);self.assertEqual((saved['kind'],saved['total'],note['credit']),('purchase_return',10000,10000))
        self.assertRegex(note['id'],r'D\d{7}$');self.assertEqual((self.balance(self.supplier),self.stock(),self.lot()),(30000,15,15))

    def test_split_payment_and_round_off(self):
        sale=self.doc(self.sale(3,payments=[{'method':'Cash','amount':50},{'method':'UPI','amount':40}]))
        self.assertEqual((sale['payment'],sale['paid'],sale['snapshot']['payments']),('Split',9000,[{'method':'Cash','amount':5000},{'method':'UPI','amount':4000}]))
        with self.assertRaises(ValueError):self.sale(1,payments=[{'method':'Cheque','amount':30}])
        with self.assertRaisesRegex(ValueError,'Select a customer'):self.sale(1,payments=[{'method':'Cash','amount':10}])
        self.shop.act('settings',{'round_off':True})
        rounded=self.doc(self.sale(3,discount=0.4));self.assertEqual((rounded['total'],rounded['snapshot']['round_off'],rounded['paid']),(9000,40,9000))
        down=self.doc(self.sale(3,discount=0.6));self.assertEqual((down['total'],down['snapshot']['round_off']),(8900,-40))

    def test_shift_counts_the_drawer_against_recorded_cash(self):
        with self.assertRaisesRegex(ValueError,'No shift is open'):self.shop.act('shift_close',{'counted':0})
        self.shop.act('shift_open',{'opening_float':500})
        with self.assertRaisesRegex(ValueError,'already open'):self.shop.act('shift_open',{'opening_float':1})
        sale=self.sale(4);self.sale(2,payments=[{'method':'Cash','amount':20},{'method':'UPI','amount':40}])
        self.sale(1,party_id=self.customer,paid=0);self.shop.act('payment',{'party_id':self.customer,'amount':30,'method':'Cash'})
        self.shop.act('expense',{'name':'Tea','amount':15,'method':'Cash'});self.shop.act('return',{'id':sale,'reason':'x','items':[{'line':0,'quantity':1}]})
        live=self.shop.state()['shift']['summary'];self.assertEqual(live['expected_cash'],50000+12000+2000+3000-1500-3000)
        report=self.shop.act('shift_close',{'counted':620,'note':'Short by five'})
        self.assertEqual((report['expected_cash'],report['counted_cash'],report['difference']),(62500,62000,-500))
        self.assertEqual((report['sales'],report['returns'],report['methods']['UPI']['in'],report['credit_given']),(3,1,4000,3000))
        state=self.shop.state();self.assertIsNone(state['shift']);self.assertEqual(state['shifts'][0]['summary']['difference'],-500)

    def test_stock_count_posts_only_the_differences(self):
        other=self.shop.act('product',{'name':'Water','sku':'W1','category':'Water','unit':'bottle','price':20,'cost':12,'stock':8,'location':'Warehouse'})['id']
        result=self.shop.act('stock_count',{'location':'Warehouse','note':'Month end','counts':[{'product_id':self.pid,'counted':18},{'product_id':other,'counted':8}]})
        self.assertEqual((result['counted'],result['adjusted'],result['variance'][0]['difference']),(2,1,-2));self.assertEqual((self.stock(),self.lot()),(18,18))
        with self.assertRaises(ValueError):self.shop.act('stock_count',{'location':'Warehouse','counts':[{'product_id':self.pid,'counted':1},{'product_id':self.pid,'counted':2}]})
        self.assertEqual(self.stock(),18)

    def test_business_settings_are_validated(self):
        for bad in ({'fssai':'123'},{'upi_id':'not a upi id'},{'composition':True,'gst_enabled':True,'gstin':'29ABCDE1234F1Z5','state':'29'}):
            with self.assertRaises(ValueError):self.shop.act('settings',bad)
        self.shop.act('settings',{'fssai':'11223344556677','upi_id':'alhadiya@okhdfcbank','composition':True})
        shop=self.doc(self.sale(1))['snapshot']['shop'];self.assertEqual((shop['fssai'],shop['upi_id'],shop['composition']),('11223344556677','alhadiya@okhdfcbank',True))

    def test_screens_load_recent_history_and_older_records_on_request(self):
        old=self.sale(1);recent=self.sale(1);credit=self.sale(2,party_id=self.customer,paid=0)
        with self.shop.connect() as db:
            db.execute("UPDATE documents SET date='2024-01-05T10:00:00+05:30' WHERE id IN (?,?)",(old,credit))
            db.execute("INSERT INTO expenses(date,name,amount,method) VALUES('2024-01-05T10:00:00+05:30','Old rent',100,'Cash')")
        state=self.shop.state();ids={d['id'] for d in state['documents']}
        self.assertIn(recent,ids);self.assertNotIn(old,ids);self.assertIn(credit,ids,'An unpaid bill stays visible whatever its age.')
        self.assertEqual((state['history']['complete'],state['expenses'],state['lines']),(False,[],[]))
        everything=self.shop.state('2000-01-01');self.assertIn(old,{d['id'] for d in everything['documents']})
        self.assertTrue(everything['history']['complete']);self.assertEqual(len(everything['expenses']),1)
        with self.assertRaises(ValueError):self.shop.state('not-a-date')
        self.shop.HISTORY_DOCUMENTS=2
        try:self.sale(1);self.sale(1);self.assertGreaterEqual(len(self.shop.state()['documents']),2)
        finally:del self.shop.HISTORY_DOCUMENTS

    def test_notes_and_their_stock_reach_another_pc(self):
        other_dir=tempfile.TemporaryDirectory();self.addCleanup(other_dir.cleanup);other=Shop(other_dir.name)
        sale=self.sale(10,party_id=self.customer,paid=100);self.shop.act('return',{'id':sale,'reason':'x','items':[{'line':0,'quantity':4}]})
        with self.shop.connect() as db:events=[{'id':r['id'],'device':r['device'],'payload':json.loads(r['payload'])} for r in db.execute('SELECT * FROM sync_events ORDER BY id')]
        with other.connect() as db:
            for event in events:other.apply_event(db,event)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM documents WHERE kind='sale_return'").fetchone()[0],1)
            self.assertEqual(db.execute('SELECT balance FROM parties WHERE id=?',(self.customer,)).fetchone()[0],8000)
            self.assertEqual(db.execute("SELECT quantity FROM lots WHERE lot='B1'").fetchone()[0],14)

if __name__=='__main__':unittest.main()
