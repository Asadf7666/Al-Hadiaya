import datetime as dt,json,tempfile,unittest
from app import Shop
import lots

def day(offset):return (dt.date.fromisoformat(lots.today())+dt.timedelta(days=offset)).isoformat()

class LotsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.shop=Shop(self.tmp.name)
        self.pid=self.shop.act('product',{'name':'Juice','sku':'J1','category':'Juices','unit':'pack','price':30,'cost':20,'location':'Warehouse'})['id']
        self.supplier=self.shop.act('party',{'name':'Distributor','kind':'supplier'})['id']
    def tearDown(self):self.tmp.cleanup()
    def buy(self,quantity,lot='',expiry='',location='Warehouse'):
        return self.shop.act('purchase',{'party_id':self.supplier,'location':location,'items':[{'product_id':self.pid,'quantity':quantity,'price':20,'lot':lot,'expiry':expiry}]})['id']
    def sell(self,quantity,location='Warehouse'):
        return self.shop.act('sale',{'location':location,'items':[{'product_id':self.pid,'quantity':quantity}]})['id']
    def held(self,location='Warehouse'):
        with self.shop.connect() as db:
            return {(r['lot'],r['expiry']):r['quantity'] for r in db.execute('SELECT * FROM lots WHERE product_id=? AND location=? AND quantity>0',(self.pid,location))}
    def stock(self,location='Warehouse'):
        with self.shop.connect() as db:
            row=db.execute('SELECT quantity FROM stocks WHERE product_id=? AND location=?',(self.pid,location)).fetchone()
            return row[0] if row else 0

    def test_one_product_holds_lots_with_different_expiry_and_sells_earliest_first(self):
        self.buy(10,'B2',day(90));self.buy(10,'B1',day(20));self.buy(5)
        self.assertEqual(self.held(),{('B2',day(90)):10,('B1',day(20)):10});self.assertEqual(self.stock(),25)
        sale=self.sell(12)
        self.assertEqual(self.held(),{('B2',day(90)):8});self.assertEqual(self.stock(),13)
        with self.shop.connect() as db:item=json.loads(db.execute('SELECT snapshot FROM documents WHERE id=?',(sale,)).fetchone()[0])['items'][0]
        self.assertEqual([(p['lot'],p['quantity']) for p in item['lots']],[('B1',10),('B2',2)])
        self.sell(10);self.assertEqual(self.held(),{});self.assertEqual(self.stock(),3,'Dated lots leave before undated stock.')
        state=self.shop.state();self.assertEqual(state['lots'],[])

    def test_expired_lot_cannot_be_sold_but_valid_lots_of_the_same_product_can(self):
        self.buy(6,'OLD',day(-2));self.buy(4,'NEW',day(60))
        with self.assertRaisesRegex(ValueError,'Only 4 pack of Juice is within expiry'):self.sell(5)
        self.assertEqual(self.stock(),10,'A refused sale changes nothing.')
        self.sell(4);self.assertEqual(self.held(),{('OLD',day(-2)):6})
        lot=next(r for r in self.shop.state()['lots'] if r['lot']=='OLD');self.assertEqual((lot['status'],lot['days']),('expired',-2))
        # Writing off clears the expired lot.
        self.shop.act('adjust',{'product_id':self.pid,'quantity':-6,'note':'Expired','location':'Warehouse','lot_id':lot['id']})
        self.assertEqual((self.held(),self.stock()),({},0))

    def test_reversal_returns_stock_to_the_same_lots(self):
        first=self.buy(10,'B1',day(20));self.buy(10,'B2',day(90));sale=self.sell(12)
        self.shop.act('reverse',{'id':sale,'reason':'Wrong bill'})
        self.assertEqual(self.held(),{('B1',day(20)):10,('B2',day(90)):10})
        self.shop.act('reverse',{'id':first,'reason':'Returned to supplier'})
        self.assertEqual((self.held(),self.stock()),({('B2',day(90)):10},10))

    def test_transfer_carries_lots_and_a_chosen_lot_is_exact(self):
        self.buy(10,'B1',day(20));self.buy(10,'B2',day(90))
        late=next(r['id'] for r in self.shop.state()['lots'] if r['lot']=='B2')
        self.shop.act('transfer',{'product_id':self.pid,'source':'Warehouse','target':'Outlet','quantity':4,'lot_id':late})
        self.assertEqual(self.held('Outlet'),{('B2',day(90)):4})
        self.shop.act('transfer',{'product_id':self.pid,'source':'Warehouse','target':'Outlet','quantity':3})
        self.assertEqual(self.held('Outlet'),{('B2',day(90)):4,('B1',day(20)):3});self.assertEqual(self.held(),{('B1',day(20)):7,('B2',day(90)):6})
        with self.assertRaisesRegex(ValueError,'holds only 6'):
            self.shop.act('transfer',{'product_id':self.pid,'source':'Warehouse','target':'Outlet','quantity':7,'lot_id':late})
        with self.assertRaisesRegex(ValueError,'no longer at this location'):
            self.shop.act('adjust',{'product_id':self.pid,'quantity':-1,'note':'x','location':'Outlet','lot_id':late})

    def test_opening_stock_found_stock_and_bad_input(self):
        pid=self.shop.act('product',{'name':'Milk','sku':'M1','category':'Dairy','unit':'pack','price':30,'cost':20,'stock':8,'location':'Outlet','lot':'OP','expiry':day(5)})['id']
        with self.shop.connect() as db:
            self.assertEqual(db.execute('SELECT expiry FROM products WHERE id=?',(pid,)).fetchone()[0],'')
            self.assertEqual(db.execute('SELECT lot,expiry,quantity FROM lots WHERE product_id=?',(pid,)).fetchone()[:],('OP',day(5),8))
        self.assertTrue(any(a['kind']=='expiry' and 'lot OP' in a['message'] for a in self.shop.state()['stock_alerts']))
        self.shop.act('adjust',{'product_id':self.pid,'quantity':2,'note':'Found','location':'Warehouse','lot':'F1','expiry':day(40)})
        self.assertEqual(self.held(),{('F1',day(40)):2})
        for bad in ({'expiry':'31-12-2027'},{'expiry':'2027-13-01'},{'lot':'x'*41}):
            with self.assertRaises(ValueError):self.buy(1,**bad)
        self.assertEqual(self.stock(),2)

    def test_single_product_expiry_from_earlier_releases_becomes_a_lot(self):
        self.buy(9)
        with self.shop.connect() as db:db.execute('UPDATE products SET expiry=? WHERE id=?',(day(-1),self.pid))
        with self.assertRaises(ValueError):self.sell(1)
        Shop(self.tmp.name)
        self.assertEqual(self.held(),{('',day(-1)):9})
        with self.shop.connect() as db:self.assertEqual(db.execute('SELECT expiry FROM products WHERE id=?',(self.pid,)).fetchone()[0],'')
        self.buy(3,'NEW',day(30));self.sell(3)
        self.assertEqual(self.held(),{('',day(-1)):9})

    def test_each_lot_keeps_its_own_mrp_and_a_bill_cannot_exceed_it(self):
        buy=lambda lot,expiry,mrp:self.shop.act('purchase',{'party_id':self.supplier,'location':'Warehouse','items':[{'product_id':self.pid,'quantity':5,'price':20,'lot':lot,'expiry':expiry,'mrp':mrp}]})
        buy('OLD',day(20),28);buy('NEW',day(200),35)
        with self.shop.connect() as db:self.assertEqual({r['lot']:r['mrp'] for r in db.execute('SELECT lot,mrp FROM lots')},{'OLD':2800,'NEW':3500})
        with self.assertRaisesRegex(ValueError,r'exceeds the MRP ₹28.00 printed on lot OLD'):self.sell(1)
        self.assertEqual(self.stock(),10)
        self.shop.act('adjust',{'product_id':self.pid,'quantity':-5,'note':'Returned old packs','location':'Warehouse'})
        self.sell(2);self.assertEqual(self.held(),{('NEW',day(200)):3})
        self.shop.act('transfer',{'product_id':self.pid,'source':'Warehouse','target':'Outlet','quantity':1})
        with self.shop.connect() as db:self.assertEqual(db.execute("SELECT mrp FROM lots WHERE location='Outlet'").fetchone()[0],3500)

    def test_lots_follow_transactions_to_another_pc(self):
        other_dir=tempfile.TemporaryDirectory();self.addCleanup(other_dir.cleanup);other=Shop(other_dir.name)
        for lot,expiry in (('B1',day(20)),('B2',day(90))):self.shop.act('purchase',{'party_id':self.supplier,'location':'Warehouse','items':[{'product_id':self.pid,'quantity':10,'price':20,'lot':lot,'expiry':expiry,'mrp':40}]})
        sale=self.sell(12);self.shop.act('reverse',{'id':sale,'reason':'x'});self.sell(3)
        with self.shop.connect() as db:events=[{'id':r['id'],'device':r['device'],'payload':json.loads(r['payload'])} for r in db.execute('SELECT * FROM sync_events ORDER BY id')]
        with other.connect() as db:
            for event in events:other.apply_event(db,event)
            copied={(r['lot'],r['expiry']):r['quantity'] for r in db.execute('SELECT * FROM lots WHERE quantity>0')}
            self.assertEqual({r['mrp'] for r in db.execute('SELECT mrp FROM lots')},{4000})
        self.assertEqual(copied,self.held());self.assertEqual(copied,{('B1',day(20)):7,('B2',day(90)):10})
        for bad in ({'product_id':self.pid,'location':'Moon','lot':'','expiry':'','delta':1},{'product_id':self.pid,'location':'Outlet','lot':'','expiry':'soon','delta':1},
                    {'product_id':self.pid,'location':'Outlet','lot':'','expiry':'','delta':float('inf')},{'product_id':self.pid,'location':'Outlet','lot':'','expiry':''}):
            with self.assertRaises(ValueError):lots.check(bad)

if __name__=='__main__':unittest.main()
