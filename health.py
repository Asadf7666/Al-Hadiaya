"""Visible, non-secret background task status; one failed task does not stop others."""
import datetime as dt,logging

def migrate(db):db.execute("CREATE TABLE IF NOT EXISTS runtime_health(component TEXT PRIMARY KEY,last_success TEXT NOT NULL DEFAULT '',last_failure TEXT NOT NULL DEFAULT '',failures INTEGER NOT NULL DEFAULT 0)")
def run(shop,component,fn):
 try:result=fn();ok=True
 except Exception:
  logging.getLogger('alhadiya').warning('Background %s did not complete; review status.',component);result=None;ok=False
 try:
  with shop.lock,shop.connect() as db:
   stamp=dt.datetime.now(dt.timezone.utc).isoformat()
   db.execute('INSERT OR IGNORE INTO runtime_health(component) VALUES(?)',(component,))
   if ok:db.execute('UPDATE runtime_health SET last_success=?,failures=0 WHERE component=?',(stamp,component))
   else:db.execute('UPDATE runtime_health SET last_failure=?,failures=failures+1 WHERE component=?',(stamp,component))
 except Exception:logging.getLogger('alhadiya').warning('Background status unavailable; other tasks will continue.')
 return result
