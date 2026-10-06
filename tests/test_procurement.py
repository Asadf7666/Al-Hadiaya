import datetime as dt,json,tempfile,unittest
from app import Shop
from activity_alerts import daily,chunks
from stock_alerts import queue
class ProcurementTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.shop=Shop(self.tmp.name)
  self.pid=self.shop.act('product',dict(name='Cola',sku='COLA',category='Cold drinks',unit='bottle',kind='stock',price=50,cost=20,stock=10,location='Warehouse',pack=24,minimum=5))['id']
  self.supplier=self.shop.act('party',{'name':'Supplier','kind':'supplier'})['id']
 def tearDown(self):self.tmp.cleanup()
 def po(self):return self.shop.act('purchase_order_create',{'supplier_id':self.supplier,'location':'Warehouse','items':[{'product_id':self.pid,'quantity':48,'price':20}]})['id']
 def receive(self,ident,qty):return self.shop.act('purchase',{'purchase_order_id':ident,'party_id':self.supplier,'location':'Warehouse','reference':'INV','paid':0,'items':[{'product_id':self.pid,'quantity':qty,'price':20}]})['id']
 def test_partial_receipts_and_reversal_change_accounts_only_at_receipt(self):
  before=self.shop.state();ident=self.po();self.assertEqual(self.shop.state()['stocks'],before['stocks']);self.assertEqual(self.shop.state()['parties'],before['parties'])
  with self.assertRaises(ValueError):self.receive(ident,12)
  self.shop.act('purchase_order_status',{'id':ident,'status':'approved'});doc=self.receive(ident,12);o=self.shop.state()['purchase_orders'][0];self.assertEqual(o['status'],'part_received');self.assertEqual(json.loads(o['items'])[0]['received'],12)
  before=self.shop.state()
  with self.assertRaises(ValueError):self.receive(ident,37)
  self.assertEqual(self.shop.state()['stocks'],before['stocks'])
  self.receive(ident,36);self.assertEqual(self.shop.state()['purchase_orders'][0]['status'],'received')
  self.shop.act('reverse',{'id':doc,'reason':'Returned receipt'});self.assertEqual(json.loads(self.shop.state()['purchase_orders'][0]['items'])[0]['received'],36)
 def test_planning_uses_demand_packs_and_open_order(self):
  self.shop.act('inventory_plan',{'product_id':self.pid,'location':'Warehouse','lead_days':2,'cover_days':14,'safety_stock':50,'enabled':True})
  row=next(r for r in self.shop.state()['inventory_planning'] if r['location']=='Warehouse');self.assertEqual(row['recommended'],48)
  ident=self.po();self.shop.act('purchase_order_status',{'id':ident,'status':'approved'});row=next(r for r in self.shop.state()['inventory_planning'] if r['location']=='Warehouse');self.assertEqual(row['incoming'],48);self.assertEqual(row['recommended'],0)
  self.shop.act('sale',{'location':'Warehouse','items':[{'product_id':self.pid,'quantity':3}]});row=next(r for r in self.shop.state()['inventory_planning'] if r['location']=='Warehouse');self.assertAlmostEqual(row['daily_demand'],.1)
 def test_same_po_concurrent_receipts_conflict_without_double_stock(self):
  ident=self.po();self.shop.act('purchase_order_status',{'id':ident,'status':'approved'})
  with self.shop.connect() as db:initial=[dict(r) for r in db.execute('SELECT * FROM sync_events ORDER BY rowid')]
  def apply(shop,e):
   with shop.connect() as db:shop.apply_event(db,{**e,'payload':json.loads(e['payload'])})
  with tempfile.TemporaryDirectory() as folder:
   peer=Shop(folder)
   for e in initial:apply(peer,e)
   self.receive(ident,12)
   peer.act('purchase',{'purchase_order_id':ident,'party_id':self.supplier,'location':'Warehouse','reference':'OTHER','paid':0,'items':[{'product_id':self.pid,'quantity':12,'price':20}]})
   with peer.connect() as db:e=dict(db.execute('SELECT * FROM sync_events ORDER BY rowid DESC LIMIT 1').fetchone())
   before=self.shop.state()
   with self.assertRaisesRegex(ValueError,'another node'):apply(self.shop,e)
   self.assertEqual(self.shop.state()['stocks'],before['stocks']);self.assertEqual(self.shop.state()['documents'],before['documents'])
 def test_stock_alerts_suppress_repeat_until_recovery_and_daily_itemises(self):
  self.shop.act('whatsapp_settings',dict(whatsapp_enabled=True,whatsapp_phone_id='123',whatsapp_api_version='v26.0',whatsapp_internal_template='staff'))
  self.shop.act('internal_contact',{'name':'Owner','phone':'9876543210','opt_in':True})
  self.shop.act('sale',{'location':'Warehouse','items':[{'product_id':self.pid,'quantity':6}]})
  def alerts():return [n for n in self.shop.state()['notifications'] if n['kind']=='low_stock']
  self.assertEqual(len(alerts()),1)
  with self.shop.connect() as db:queue(self.shop,db);queue(self.shop,db)
  self.assertEqual(len(alerts()),1)
  self.shop.act('adjust',{'product_id':self.pid,'location':'Warehouse','quantity':10,'note':'Restock'})
  self.shop.act('sale',{'location':'Warehouse','items':[{'product_id':self.pid,'quantity':10}]});self.assertEqual(len(alerts()),2)
  with self.shop.connect() as db:text=daily(self.shop,db,dt.datetime.now(dt.timezone.utc))
  self.assertIn('Sold Cola: 16 bottle',text);self.assertIn('Stock deducted: Cola',text);self.assertIn('Customer outstanding',text)
  pages=chunks('\n'.join('Line '+str(i)+' '+('x'*100) for i in range(100)));self.assertTrue(all(len(p)<=2800 for p in pages));self.assertEqual('\n'.join(pages),'\n'.join('Line '+str(i)+' '+('x'*100) for i in range(100)))
 def test_purchase_order_valid_receipt_syncs_to_another_full_node(self):
  ident=self.po();self.shop.act('purchase_order_status',{'id':ident,'status':'approved'});self.receive(ident,24)
  with self.shop.connect() as db:events=[dict(r) for r in db.execute('SELECT * FROM sync_events ORDER BY rowid')]
  with tempfile.TemporaryDirectory() as folder:
   peer=Shop(folder)
   for e in events:
    with peer.connect() as db:peer.apply_event(db,{**e,'payload':json.loads(e['payload'])})
   self.assertEqual(peer.state()['purchase_orders'],self.shop.state()['purchase_orders']);self.assertEqual(peer.state()['products'][0]['stock'],34);self.assertEqual(peer.state()['parties'][0]['balance'],48000)
 def test_expiry_alert_and_location_stockout_are_visible(self):
  from stock_alerts import alerts
  expiry=(dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=3)).isoformat()
  with self.shop.connect() as db:
   db.execute('UPDATE products SET expiry=? WHERE id=?',(expiry,self.pid));db.execute('INSERT INTO stocks VALUES(?,?,?)',(self.pid,'Outlet',0));rows=alerts(db,self.shop.settings(db))
  self.assertTrue(any(a['kind']=='expiry' and a['location']=='Warehouse' for a in rows));self.assertTrue(any(a['kind']=='stockout' and a['location']=='Outlet' for a in rows))
