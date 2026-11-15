import json,os,tempfile,unittest
from unittest import mock
from app import Shop
import receipt_printer as rp

class ReceiptPrinterTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.shop=Shop(self.tmp.name)
        self.shop.act('settings',{'name':'Al Hadiya Traders','address':'12 Market Road, Mangaluru','phone':'9000000000','fssai':'11223344556677','upi_id':'alhadiya@okhdfcbank'})
        self.pid=self.shop.act('product',{'name':'Mango Juice 200 ml Tetra Pack Family Saver Extra Long Name','sku':'J1','category':'Juices','unit':'pack','price':30,'cost':20,'stock':20,'location':'Warehouse'})['id']
        self.customer=self.shop.act('party',{'name':'Hotel Sagar','kind':'customer'})['id']
    def tearDown(self):self.tmp.cleanup()
    def doc(self,ident):
        with self.shop.connect() as db:row=dict(db.execute('SELECT * FROM documents WHERE id=?',(ident,)).fetchone())
        row['snapshot']=json.loads(row['snapshot']);return row
    def lines(self,data):
        text=data
        for code in (rp.INIT,rp.CENTRE,rp.LEFT,rp.BOLD,rp.PLAIN,rp.LARGE,rp.NORMAL,rp.CUT,rp.DRAWER):text=text.replace(code,b'')
        return text.decode('cp437').split('\n')

    def test_bill_fits_every_paper_width_and_carries_the_legal_lines(self):
        sale=self.doc(self.shop.act('sale',{'location':'Warehouse','party_id':self.customer,'paid':100,'items':[{'product_id':self.pid,'quantity':10}]})['id'])
        for columns in rp.COLUMNS:
            data=rp.receipt(sale,columns);start=data.index(b'\x1d(k');end=data.index(b'\x1d(k\x03\x001Q0')+8
            lines=self.lines(data[:start]+data[end:])
            self.assertTrue(all(len(line)<=int(columns) for line in lines),(columns,max(lines,key=len)))
            text='\n'.join(lines)
            for expected in ('Al Hadiya Traders','FSSAI Lic. No. 11223344556677','SALE RECEIPT','No: '+sale['id'],'Customer: Hotel Sagar','300.00','Paid - Cash','Balance due','Scan to pay Rs.200.00'):
                self.assertIn(expected,text,(columns,expected))
            self.assertTrue(data.startswith(rp.INIT) and data.endswith(rp.CUT))
            self.assertIn(b'upi://pay?pa=alhadiya%40okhdfcbank&pn=Al%20Hadiya%20Traders&am=200.00&cu=INR&tn='+sale['id'].encode(),data)
            length=len(b'upi://pay?pa=alhadiya%40okhdfcbank&pn=Al%20Hadiya%20Traders&am=200.00&cu=INR&tn='+sale['id'].encode())+3
            self.assertIn(b'\x1d(k'+bytes([length%256,length//256])+b'1P0',data)
        self.assertNotIn('₹'.encode('utf-8'),rp.receipt(sale))

    def test_drawer_opens_only_for_cash_and_notes_are_titled(self):
        cash=self.doc(self.shop.act('sale',{'location':'Warehouse','items':[{'product_id':self.pid,'quantity':1}]})['id'])
        upi=self.doc(self.shop.act('sale',{'location':'Warehouse','payment':'UPI','items':[{'product_id':self.pid,'quantity':1}]})['id'])
        self.assertTrue(rp.receipt(cash,48,True).endswith(rp.DRAWER));self.assertFalse(rp.receipt(cash,48,False).endswith(rp.DRAWER));self.assertFalse(rp.receipt(upi,48,True).endswith(rp.DRAWER))
        note=self.doc(self.shop.act('return',{'id':cash['id'],'reason':'Leaking','items':[{'line':0,'quantity':1}]})['id'])
        text='\n'.join(self.lines(rp.receipt(note,32)))
        for expected in ('CREDIT NOTE','Against: '+cash['id'],'Reason: Leaking','Refunded - Cash'):self.assertIn(expected,text)

    def test_actions_send_to_the_chosen_printer_and_fail_clearly_without_one(self):
        sale=self.shop.act('sale',{'location':'Warehouse','items':[{'product_id':self.pid,'quantity':1}]})['id']
        with self.assertRaisesRegex(ValueError,'Choose a receipt printer'):self.shop.act('print_receipt',{'id':sale})
        with self.assertRaises(ValueError):self.shop.act('settings',{'receipt_columns':'99'})
        self.shop.act('settings',{'receipt_printer':'TVS RP 3160','receipt_columns':'42','drawer_kick':True})
        with mock.patch.object(rp,'send') as send:
            self.assertEqual(self.shop.act('print_receipt',{'id':sale}),{'ok':True,'printer':'TVS RP 3160'})
            name,data=send.call_args[0];self.assertEqual(name,'TVS RP 3160');self.assertTrue(data.endswith(rp.DRAWER))
            self.shop.act('print_receipt',{'id':sale,'reprint':True});self.assertFalse(send.call_args[0][1].endswith(rp.DRAWER))
            self.shop.act('print_test',{});self.assertIn(b'Receipt printer test',send.call_args[0][1])
            self.shop.act('open_drawer',{});self.assertEqual(send.call_args[0][1],rp.DRAWER)
            self.shop.act('shift_open',{'opening_float':100});shift=self.shop.act('shift_close',{'counted':100})['id']
            self.shop.act('print_shift',{'id':shift});self.assertIn(b'DAY-END REPORT',send.call_args[0][1])
            with self.assertRaisesRegex(ValueError,'Bill not found'):self.shop.act('print_receipt',{'id':'nope'})
        # Unmocked: no such printer on Windows, and no spooler at all elsewhere.
        with self.assertRaisesRegex(ValueError,'was not found' if os.name=='nt' else 'Windows app'):self.shop.act('print_test',{})
        self.assertIsInstance(self.shop.state()['printers'],list)

if __name__=='__main__':unittest.main()
