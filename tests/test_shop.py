import json
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Shop, money, restore_backup

class ShopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.shop = Shop(self.root/'shop')
    def tearDown(self):
        self.temp.cleanup()
    def product(self, **kwargs):
        data = dict(name='Test drink',sku='DRINK',category='Cold drinks',unit='bottle',kind='stock',price=140,cost=70,
                    gst=40,cess=0,hsn='220210',tax_verified=True,stock=100,location='Outlet',pack=24)
        data.update(kwargs)
        return self.shop.act('product',data)['id']
    def customer(self,kind='customer'):
        return self.shop.act('party',{'name':'Test party','kind':kind})['id']
    def enable_gst(self):
        self.shop.act('settings',{'gst_enabled':True,'gstin':'29ABCDE1234F1Z5','state':'29'})
    def sale(self,pid,quantity=1,**kw):
        data={'items':[{'product_id':pid,'quantity':quantity}],'payment':'Cash','location':'Outlet'}
        data.update(kw)
        return self.shop.act('sale',data)['id']
    def test_money_rounding(self):
        self.assertEqual(money('1.005'),101)
        for v in ('NaN','Infinity','-1'):
            with self.assertRaises(ValueError):money(v)
    def test_gst_inclusive_and_invoice_length(self):
        p=self.product();self.enable_gst();i=self.sale(p)
        d=self.shop.state()['documents'][0];line=d['snapshot']['items'][0]
        self.assertEqual((d['total'],d['tax'],line['taxable'],line['cgst_amount'],line['sgst_amount']),(14000,4000,10000,2000,2000))
        self.assertLessEqual(len(i),16)
        self.assertEqual(self.shop.state()['products'][0]['stock'],99)
    def test_igst_and_snapshot_stability(self):
        p=self.product();self.enable_gst();self.sale(p,supply_state='27')
        d=self.shop.state()['documents'][0]
        self.assertEqual(d['snapshot']['items'][0]['igst_amount'],4000)
        self.shop.act('settings',{'name':'New name'})
        self.assertEqual(self.shop.state()['documents'][0]['snapshot']['shop']['name'],'Al Hadiya Traders')
    def test_small_tax_rounding_never_negative(self):
        p=self.product(price=.03,gst=18);self.enable_gst();self.sale(p)
        i=self.shop.state()['documents'][0]['snapshot']['items'][0]
        self.assertGreaterEqual(i['cess_amount'],0)
        self.assertEqual(i['tax'],i['cgst_amount']+i['sgst_amount']+i['igst_amount']+i['cess_amount'])
    def test_gst_disabled(self):
        p=self.product();self.sale(p)
        self.assertEqual(self.shop.state()['documents'][0]['tax'],0)
    def test_discount_allocation_and_cess(self):
        p=self.product(price=140,gst=28,cess=12);self.enable_gst();self.sale(p,quantity=2,discount=28)
        d=self.shop.state()['documents'][0];i=d['snapshot']['items'][0]
        self.assertEqual((d['total'],d['tax'],i['taxable'],i['gst_amount'],i['cess_amount']),(25200,7200,18000,5040,2160))
    def test_overselling_rolls_back_whole_sale(self):
        p=self.product(stock=2);q=self.product(sku='SECOND',stock=0)
        with self.assertRaises(ValueError):self.shop.act('sale',{'items':[{'product_id':p,'quantity':1},{'product_id':q,'quantity':1}]})
        s=self.shop.state()
        self.assertFalse(s['documents']);self.assertEqual(next(x for x in s['products'] if x['id']==p)['stock'],2)
    def test_customer_credit_and_payment(self):
        p=self.product();c=self.customer();self.sale(p,party_id=c,paid=40)
        self.assertEqual(self.shop.state()['parties'][0]['balance'],10000)
        self.shop.act('payment',{'party_id':c,'amount':60,'method':'UPI'})
        self.assertEqual(self.shop.state()['parties'][0]['balance'],4000)
        with self.assertRaises(ValueError):self.shop.act('payment',{'party_id':c,'amount':41,'method':'UPI'})
    def test_walkin_credit_rejected(self):
        p=self.product()
        with self.assertRaises(ValueError):self.sale(p,paid=1)
        self.assertEqual(self.shop.state()['products'][0]['stock'],100)
    def test_purchase_weighted_cost(self):
        p=self.product(stock=10,cost=10);supplier=self.customer('supplier')
        self.shop.act('purchase',{'party_id':supplier,'location':'Outlet','paid':0,'items':[{'product_id':p,'quantity':10,'price':20}]})
        s=self.shop.state();self.assertEqual((s['products'][0]['stock'],s['products'][0]['cost']),(20,1500))
        self.assertEqual(s['parties'][0]['balance'],20000)
    def test_transfer_conserves_stock(self):
        p=self.product(location='Warehouse');self.shop.act('transfer',{'product_id':p,'quantity':24,'source':'Warehouse','target':'Outlet'})
        s=self.shop.state();self.assertEqual(s['products'][0]['stock'],100)
        self.assertEqual({r['location']:r['quantity'] for r in s['stocks']},{'Warehouse':76,'Outlet':24})
    def test_recipe_consumption_and_full_reversal(self):
        milk=self.product(sku='MILK',name='Milk',kind='ingredient',unit='ml',stock=1000,cost=.1)
        cafe=self.product(sku='COFFEE',name='Coffee',kind='recipe',unit='cup',stock=0,price=50)
        self.shop.act('recipe',{'product_id':cafe,'items':[{'ingredient_id':milk,'quantity':150}]})
        d=self.sale(cafe,2);self.assertEqual(next(p for p in self.shop.state()['products'] if p['id']==milk)['stock'],700)
        self.shop.act('reverse',{'id':d,'reason':'Cancelled before preparation'})
        self.assertEqual(next(p for p in self.shop.state()['products'] if p['id']==milk)['stock'],1000)
        with self.assertRaises(ValueError):self.shop.act('reverse',{'id':d,'reason':'Again'})
    def test_reversal_after_payment_is_blocked(self):
        p=self.product();c=self.customer();d=self.sale(p,party_id=c,paid=0)
        self.shop.act('payment',{'party_id':c,'amount':10,'method':'Cash'})
        with self.assertRaises(ValueError):self.shop.act('reverse',{'id':d,'reason':'Return'})
    def test_backup_and_restore(self):
        p=self.product();backup=self.shop.backup()['paths'][0];self.sale(p)
        restore_backup(self.shop,backup)
        self.assertFalse(self.shop.state()['documents']);self.assertEqual(self.shop.state()['products'][0]['stock'],100)
        with closing(sqlite3.connect(backup)) as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
    def test_two_pc_offline_sync_idempotency_and_convergence(self):
        # Keep test setup small; the actual Warehouse setup populates the catalogue.
        p=self.product(location='Warehouse');self.customer('supplier')
        cloud=str(self.root/'cloud');self.shop.act('settings',{'device_location':'Warehouse','sync_folder':cloud})
        outlet=Shop(self.root/'outlet');outlet.act('settings',{'device_location':'Outlet','sync_folder':cloud})
        self.shop.act('transfer',{'product_id':p,'quantity':24,'source':'Warehouse','target':'Outlet'})
        self.shop.sync();self.assertEqual(outlet.sync()['pending'],0)
        outlet.act('sale',{'location':'Outlet','payment':'Cash','items':[{'product_id':p,'quantity':3}]})
        self.assertEqual(self.shop.state()['products'][0]['stock'],100)
        outlet.sync();self.assertEqual(self.shop.sync()['pending'],0)
        for _ in range(2):outlet.sync();self.shop.sync()
        a,b=self.shop.state(),outlet.state()
        self.assertEqual(a['products'],b['products']);self.assertEqual(len(a['documents']),1);self.assertEqual(len(b['documents']),1)
        self.assertEqual(a['products'][0]['stock'],97)
        self.assertEqual(sorted(a['stocks'],key=lambda s:s['location']),sorted(b['stocks'],key=lambda s:s['location']))
    def test_every_node_can_manage_both_locations(self):
        p=self.product();self.shop.act('settings',{'device_location':'Outlet','setup_role':'join'})
        self.shop.act('adjust',{'product_id':p,'location':'Warehouse','quantity':10,'note':'test'})
        self.shop.act('transfer',{'product_id':p,'source':'Warehouse','target':'Outlet','quantity':1})
        q=self.product(sku='OTHER');self.assertTrue(q)
        self.shop.act('party',{'kind':'supplier','name':'Supplier from cafe node'})
        self.shop.act('settings',{'name':'Shared business edited at cafe'})
        self.assertEqual(self.shop.state()['settings']['name'],'Shared business edited at cafe')
    def test_duplicate_barcode_and_bulk_import_are_atomic(self):
        self.product(barcode='12345')
        with self.assertRaises(sqlite3.IntegrityError):self.product(sku='OTHER',barcode='12345')
        self.assertEqual(len(self.shop.state()['products']),1)
        with self.assertRaises(ValueError):self.shop.act('import_products',{'rows':[dict(name='Good',sku='NEW',category='Water',unit='bottle'),dict(name='',sku='BAD',category='Water',unit='bottle')]})
        self.assertEqual(len(self.shop.state()['products']),1)
    def test_mrp_and_wholesale(self):
        p=self.product(price=140,mrp=150,wholesale_price=100)
        self.sale(p,price_tier='wholesale')
        self.assertEqual(self.shop.state()['documents'][0]['total'],10000)
        self.product(id=p,price=160,mrp=150)
        with self.assertRaises(ValueError):self.sale(p)
    def test_catalogue_zero_stock_unverified_rates(self):
        r=self.shop.act('catalog',{})
        self.assertGreater(r['count'],300)
        self.assertTrue(all(p['stock']==0 and p['price']==0 and p['barcode']=='' and p['tax_verified']==0 for p in self.shop.state()['products']))
        self.assertEqual(self.shop.act('catalog',{})['count'],0)
    def test_warehouse_setup_loads_catalogue(self):
        self.shop.act('settings',{'device_location':'Warehouse'})
        self.assertGreater(len(self.shop.state()['products']),300)
    def test_warehouse_bills_trading_customers(self):
        p=self.product(location='Warehouse',wholesale_price=100)
        self.shop.act('settings',{'device_location':'Warehouse'})
        self.shop.act('sale',{'location':'Warehouse','price_tier':'wholesale','items':[{'product_id':p,'quantity':24}]})
        s=self.shop.state();self.assertEqual(s['documents'][0]['total'],240000)
        self.assertEqual(s['products'][0]['stock'],76)
    def test_partial_csv_update_preserves_existing_attributes(self):
        p=self.product(barcode='12345',brand='Test brand')
        self.shop.act('import_products',{'rows':[{'sku':'DRINK','name':'Renamed drink'}]})
        q=self.shop.state()['products'][0]
        self.assertEqual((q['id'],q['price'],q['stock'],q['barcode'],q['brand']),(p,14000,100,'12345','Test brand'))
    def test_sync_stock_conflict_is_visible_and_atomic(self):
        p=self.product();self.shop.act('settings',{'device_location':'Outlet','sync_folder':str(self.root/'cloud')})
        self.shop.sync()
        event={'version':1,'id':'99999999999999999999-foreign','date':'','device':'foreign','payload':{'masters':{},'deltas':{'stocks':[{'product_id':p,'location':'Outlet','delta':-1000}],'parties':[]},'append':{},'recipes':[],'settings':[]}}
        path=self.root/'cloud'/'AlHidayaSync-v1'/(event['id']+'.json');path.write_text(json.dumps(event))
        self.assertEqual(self.shop.sync()['pending'],1)
        self.assertEqual(self.shop.state()['products'][0]['stock'],100)
        self.assertEqual(len(self.shop.state()['sync_errors']),1)

    def test_conflicting_offline_stock_is_preserved_for_review(self):
        p=self.product(stock=10,location='Warehouse');cloud=str(self.root/'cloud')
        self.shop.act('settings',{'device_location':'Warehouse','sync_folder':cloud})
        other=Shop(self.root/'other');other.act('settings',{'device_location':'Outlet','sync_folder':cloud})
        self.shop.sync();other.sync()
        self.shop.act('sale',{'location':'Warehouse','items':[{'product_id':p,'quantity':6}]})
        other.act('sale',{'location':'Warehouse','items':[{'product_id':p,'quantity':6}]})
        other.sync();r=self.shop.sync()
        self.assertGreater(r['pending'],0);self.assertEqual(self.shop.state()['products'][0]['stock'],4)
        self.assertEqual(len(other.state()['documents']),1)
        self.assertTrue(self.shop.state()['sync_errors'])
    def test_customer_profile_updates_preserve_history_and_dues(self):
        p=self.product();c=self.customer();self.sale(p,party_id=c,paid=40)
        self.shop.act('party',{'id':c,'kind':'customer','name':'Updated customer','phone':'9876543210','email':'customer@example.test',
            'address':'Bengaluru','notes':'Weekly orders','price_tier':'wholesale','credit_limit':500})
        profile=self.shop.state()['parties'][0]
        self.assertEqual((profile['balance'],profile['name'],profile['credit_limit']),(10000,'Updated customer',50000))
        self.assertEqual(self.shop.state()['documents'][0]['party_id'],c)
        self.assertEqual(self.shop.state()['documents'][0]['snapshot']['party']['name'],'Test party')
        with self.assertRaises(ValueError):self.sale(p,quantity=5,party_id=c,paid=0)

    def test_any_node_can_reverse_a_synced_invoice(self):
        p=self.product(stock=10,location='Warehouse');cloud=str(self.root/'cloud')
        self.shop.act('settings',{'device_location':'Warehouse','sync_folder':cloud})
        bill=self.shop.act('sale',{'location':'Warehouse','items':[{'product_id':p,'quantity':2}]})['id']
        other=Shop(self.root/'other');other.act('settings',{'device_location':'Outlet','sync_folder':cloud})
        self.shop.sync();other.sync()
        other.act('reverse',{'id':bill,'reason':'Reversed from another node'})
        other.sync();self.shop.sync()
        self.assertTrue(self.shop.state()['documents'][0]['reversed']);self.assertEqual(self.shop.state()['products'][0]['stock'],10)

if __name__=='__main__':unittest.main()
