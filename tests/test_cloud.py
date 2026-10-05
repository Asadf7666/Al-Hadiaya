import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cloud.server import Online
class WebTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.online=Online(Path(self.temp.name),'http://localhost',False)
  self.online.user({'username':'owner','password':'test-owner-password','role':'owner'})
 def tearDown(self):self.temp.cleanup()
 def test_login_wrong_password_and_session(self):
  self.assertIsNone(self.online.login('owner','wrong','ip'))
  token=self.online.login('owner','test-owner-password','ip')
  user=self.online.session('ah_session='+token)
  self.assertEqual(user['role'],'owner');self.assertTrue(user['csrf'])
 def test_cashier_cannot_administer_stock_or_escape_location(self):
  self.online.user({'username':'till','password':'test-till-password','role':'cashier','location':'Outlet'})
  u=self.online.session('ah_session='+self.online.login('till','test-till-password','ip'))
  with self.assertRaises(PermissionError):self.online.act(u,'adjust',{})
  with self.assertRaises(PermissionError):self.online.act(u,'staff_user',{})
  pid=self.online.shop.act('product',{'name':'Drink','sku':'DR','category':'Cold drinks','unit':'bottle','kind':'stock','price':50,'cost':20,'stock':5,'location':'Warehouse'})['id']
  with self.assertRaises(ValueError):self.online.act(u,'sale',{'location':'Warehouse','items':[{'product_id':pid,'quantity':1}]})
 def test_viewer_cannot_write_and_staff_cannot_see_notifications(self):
  user={'role':'viewer','username':'viewer','name':'Viewer','location':'Outlet'}
  with self.assertRaises(PermissionError):self.online.act(user,'sale',{})
  state=self.online.state(user)
  self.assertFalse(state['local']);self.assertEqual(state['notifications'],[])
 def test_rate_limit(self):
  for _ in range(8):self.assertIsNone(self.online.login('owner','wrong','ip'))
  self.assertIsNone(self.online.login('owner','test-owner-password','ip'))
