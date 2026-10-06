"""Portable database/photo snapshots and guarded local recovery; credentials excluded."""
import base64,io,json,pathlib,shutil,sqlite3,tempfile,zipfile,uuid
from contextlib import closing
MAX_BYTES=64*1024*1024

def bundle(shop):
 snapshot=pathlib.Path(shop.backup(local_only=True)['paths'][0]);out=io.BytesIO()
 with tempfile.TemporaryDirectory() as folder,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  portable=pathlib.Path(folder)/'shop.sqlite3';shutil.copyfile(snapshot,portable)
  with closing(sqlite3.connect(portable)) as db:
   tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   for table in ('web_sessions','web_audit','web_users','cloud_codes','cloud_peers','whatsapp_sender_check'):
    if table in tables:db.execute('DELETE FROM '+table)
   db.commit()
  z.writestr('manifest.json',json.dumps({'format':1,'business':'Al Hadiya Traders','credentials_included':False}))
  z.write(portable,'shop.sqlite3')
  media=snapshot.with_suffix('.media')
  if media.exists():
   for p in media.iterdir():
    if p.is_file():z.write(p,'media/'+p.name)
 return out.getvalue()
def restore(shop,data):
 if data.get('confirm')!='RESTORE':raise ValueError('Type RESTORE to replace business records after a safety backup.')
 try:raw=base64.b64decode(data['content'],validate=True)
 except Exception:raise ValueError('Choose a valid backup ZIP.') from None
 if len(raw)>MAX_BYTES:raise ValueError('Backup exceeds 64 MB. Use assisted recovery for a larger archive.')
 with shop.cloud_lock,shop.lock,tempfile.TemporaryDirectory() as folder:
  try:
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    infos=z.infolist()
    if sum(i.file_size for i in infos)>MAX_BYTES or len(infos)>2000:raise ValueError('Backup expands beyond the recovery limit.')
    names=set()
    for i in infos:
     path=pathlib.PurePosixPath(i.filename)
     if i.filename in names or '\\' in i.filename or i.filename!=str(path) or path.is_absolute() or '..' in path.parts or i.is_dir() or (i.filename not in ('manifest.json','shop.sqlite3') and not (len(path.parts)==2 and path.parts[0]=='media' and path.name==path.name.lower() and path.suffix in ('.jpg','.png'))):raise ValueError('Unsafe backup archive member.')
     names.add(i.filename)
    manifest=json.loads(z.read('manifest.json'))
    if manifest.get('format')!=1 or manifest.get('credentials_included') is not False:raise ValueError('Unsupported backup format.')
    z.extractall(folder)
  except (zipfile.BadZipFile,KeyError,json.JSONDecodeError):raise ValueError('Invalid backup ZIP.') from None
  source=pathlib.Path(folder)/'shop.sqlite3'
  with closing(sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True)) as db:
   if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup database integrity failed.')
   tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   if not {'products','documents','settings','audit','stocks','sync_seen'}<=tables:raise ValueError('Not an Al Hadiya business backup.')
  with shop.connect() as db:
   settings=shop.settings(db)
   if settings.get('cloud_url') or settings.get('sync_folder'):raise ValueError('Disconnect and reconcile sync before restoring; use assisted recovery for paired nodes.')
   users=[dict(r) for r in db.execute('SELECT * FROM web_users')] if 'web_users' in {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} else []
  safety=shop.backup(local_only=True)
  media=shop.folder/'media';staged=shop.folder/('.restore-media-'+uuid.uuid4().hex);old=shop.folder/('.restore-old-'+uuid.uuid4().hex);had_media=media.exists();swapped=False
  # Stage photos on the same filesystem before changing business records.
  try:
   shutil.copytree(pathlib.Path(folder)/'media',staged) if (pathlib.Path(folder)/'media').exists() else staged.mkdir()
   with closing(sqlite3.connect(source)) as db,shop.connect() as target:db.backup(target)
   from app import Shop
   Shop(shop.folder)
   from staff_access import StaffAccess
   StaffAccess(shop.folder,'http://localhost',False,local=True,shop=shop)
   with shop.connect() as db:
    for key,value in {'device_id':settings['device_id'],'device_name':settings.get('device_name',''),'device_location':settings.get('device_location',''),'cloud_url':'','cloud_business_id':'','cloud_cursor':0,'sync_folder':'','whatsapp_enabled':False}.items():db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
    db.execute('DELETE FROM web_sessions');db.execute('DELETE FROM web_audit');db.execute('DELETE FROM web_users')
    for u in users:
     cols=list(u);db.execute('INSERT INTO web_users('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',tuple(u.values()))
   if media.exists():media.rename(old)
   staged.rename(media)
   swapped=True
   with shop.connect() as db:shop.audit(db,'restore_bundle',{'safety_backup':safety['paths'][0]})
  except Exception:
   with closing(sqlite3.connect(safety['paths'][0])) as db,shop.connect() as target:db.backup(target)
   if old.exists():
    if media.exists():shutil.rmtree(media)
    old.rename(media)
   elif swapped and not had_media:shutil.rmtree(media)
   raise ValueError('Recovery could not complete. Previous records were restored; keep the safety backup.') from None
  finally:
   if staged.exists():shutil.rmtree(staged,ignore_errors=True)
  if old.exists():shutil.rmtree(old,ignore_errors=True)
 return {'message':'Backup restored. Sign in again. WhatsApp and sync remain off until checked.','safety_backup':safety['paths'][0]}
