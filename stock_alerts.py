"""Location-aware stock alerts with persistent episode suppression."""
import datetime as dt,json

def alerts(db,settings):
 from outreach import business_now
 from procurement import planning
 day=business_now(settings).date();policies={(r['product_id'],r['location']):r for r in db.execute('SELECT * FROM inventory_plans')};planned={(r['product_id'],r['location']):r for r in planning(db)};result=[]
 for p in db.execute("SELECT * FROM products WHERE kind<>'recipe' AND (price>0 OR cost>0 OR stock>0 OR id IN (SELECT product_id FROM inventory_plans))"):
  for location in ('Warehouse','Outlet'):
   key=(p['id'],location);policy=policies.get(key)
   stocked=db.execute('SELECT quantity FROM stocks WHERE product_id=? AND location=?',key).fetchone()
   if not stocked and not policy:continue
   quantity=stocked[0] if stocked else 0;threshold=policy['safety_stock'] if policy else p['minimum'];plan=planned.get(key,{})
   if quantity<=threshold:
    kind='stockout' if quantity<=0 else 'low_stock';message=f"{p['name']} ({location})\nAvailable: {quantity:g} {p['unit']}\nAlert level: {threshold:g} {p['unit']}"
    if plan.get('recommended'):message+=f"\nSuggested order: {plan['recommended']:g} {p['unit']}\nPack size: {p['pack']:g} | Incoming: {plan['incoming']:g}"
    if plan.get('transfer_available'):message+=f"\nAvailable transfer: {plan['transfer_available']:g} from Warehouse"
    result.append({'key':f'{kind}:{p["id"]}:{location}','kind':kind,'product_id':p['id'],'location':location,'message':message})
   elif plan.get('urgent'):
    result.append({'key':f'reorder:{p["id"]}:{location}','kind':'reorder','product_id':p['id'],'location':location,'message':f"{p['name']} ({location})\nAvailable: {quantity:g} {p['unit']}\nSupply left: {plan['days_remaining']} days\nSupplier lead time: {plan['lead_days']} days\nSuggested: {plan['recommended']:g} | Incoming: {plan['incoming']:g}"})
   if p['expiry'] and quantity>0:
    days=(dt.date.fromisoformat(p['expiry'])-day).days
    if days<=7:
     kind='expired' if days<0 else 'expiry';result.append({'key':f'{kind}:{p["id"]}:{location}:{p["expiry"]}','kind':kind,'product_id':p['id'],'location':location,'message':f"{p['name']} ({location})\nAvailable: {quantity:g} {p['unit']}\nRecorded expiry: {p['expiry']} ({days} days)\nReview affected stock. Expiry is recorded per SKU."})
 return result

def queue(shop,db):
 s=shop.settings(db)
 if not s.get('whatsapp_enabled') or not s.get('whatsapp_low_stock'):return
 db.execute('CREATE TABLE IF NOT EXISTS stock_alert_state(key TEXT PRIMARY KEY,active INTEGER NOT NULL,episode INTEGER NOT NULL DEFAULT 0)')
 current=alerts(db,s);keys={a['key'] for a in current}
 for r in db.execute('SELECT key FROM stock_alert_state WHERE active=1').fetchall():
  if r['key'] not in keys:db.execute('UPDATE stock_alert_state SET active=0 WHERE key=?',(r['key'],))
 for a in current:
  old=db.execute('SELECT * FROM stock_alert_state WHERE key=?',(a['key'],)).fetchone()
  episode=(old['episode'] if old else 0)+(0 if old and old['active'] else 1)
  db.execute('INSERT OR REPLACE INTO stock_alert_state VALUES(?,1,?)',(a['key'],episode))
  for recipient in db.execute('SELECT * FROM internal_contacts WHERE opt_in=1'):
   shop.notification(db,f"stock-alert:{a['key']}:{episode}:{recipient['id']}",a['kind'],recipient['phone'],s['whatsapp_internal_template'],[s['name'],a['kind'].replace('_',' ').title(),a['message']],internal_id=recipient['id'])
