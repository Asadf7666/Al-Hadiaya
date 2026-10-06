"""Owner-approved campaigns and signed WhatsApp delivery webhooks."""
import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
import urllib.request
import urllib.error
from pathlib import Path
from notifications import whatsapp_number, protect, read_token


def migrate(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS whatsapp_campaigns(id TEXT PRIMARY KEY,name TEXT NOT NULL,created TEXT NOT NULL,
        template TEXT NOT NULL,language TEXT NOT NULL,offer TEXT NOT NULL,recipients TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',scheduled TEXT NOT NULL DEFAULT '',approved TEXT NOT NULL DEFAULT '');
      CREATE TABLE IF NOT EXISTS whatsapp_templates(name TEXT NOT NULL,language TEXT NOT NULL,status TEXT NOT NULL,
        category TEXT NOT NULL,body TEXT NOT NULL,supported INTEGER NOT NULL,checked TEXT NOT NULL,PRIMARY KEY(name,language));
      CREATE TABLE IF NOT EXISTS whatsapp_receipts(provider_id TEXT PRIMARY KEY,status TEXT NOT NULL,timestamp INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS whatsapp_inbound(id TEXT PRIMARY KEY,created TEXT NOT NULL);
    ''')
    from media_catalogue import migrate as migrate_media
    migrate_media(db)
    for key,kind,default in [('campaign_id','TEXT',"''"),('language','TEXT',"''")]:
        if key not in {r[1] for r in db.execute('PRAGMA table_info(notifications)')}:
            db.execute('ALTER TABLE notifications ADD COLUMN '+key+' '+kind+' NOT NULL DEFAULT '+default)


def business_now(settings):
    # Fixed offsets avoid requiring the Windows embedded Python to install tzdata.
    zone=dt.timezone(dt.timedelta(hours=5,minutes=30)) if settings.get('whatsapp_timezone','Asia/Kolkata')=='Asia/Kolkata' else dt.timezone.utc
    return dt.datetime.now(zone)


def secret_path(folder):return Path(folder)/'whatsapp-webhook-credential.bin'
def webhook_configured(folder):return secret_path(folder).is_file()
def read_webhook(folder):
    p=secret_path(folder)
    return json.loads(protect(p.read_bytes(),decrypt=True)) if p.exists() else {}

def save_webhook(folder,data):
    old=read_webhook(folder)
    for key in ('app_secret','verify_token'):
        value=str(data.get(key,'')).strip() or old.get(key,'')
        if len(value)<16 or len(value)>256:raise ValueError('Enter an app secret and a verification token of at least 16 characters.')
        old[key]=value
    p=secret_path(folder);tmp=p.with_suffix('.tmp')
    tmp.touch(mode=0o600,exist_ok=True)
    with tmp.open('wb') as f:f.write(protect(json.dumps(old).encode()))
    if __import__('os').name!='nt':tmp.chmod(0o600)
    tmp.replace(p)


def supported_template(components):
    body=next((c.get('text','') for c in components if c.get('type')=='BODY'),'')
    variables=set(re.findall(r'\{\{(\d+)\}\}',body))
    supported=variables in (set(),{'1','2','3'})
    for c in components:
        if c.get('type')=='HEADER' and (c.get('format') not in ('TEXT','IMAGE') or '{{' in c.get('text','')):supported=False
        if c.get('type')=='CAROUSEL':supported=False
        if c.get('type')=='BUTTONS' and any('{{' in str(b) or b.get('type')=='FLOW' for b in c.get('buttons',[])):supported=False
    return body,supported


def refresh_templates(shop):
    with shop.lock,shop.connect() as db:s=shop.settings(db)
    token=read_token(shop.folder)
    if not token or not re.fullmatch(r'\d+',s.get('whatsapp_waba_id','')) or not re.fullmatch(r'v\d+\.\d+',s.get('whatsapp_api_version','')):
        raise ValueError('Configure the token, Business Account ID and API version first.')
    url=f"https://graph.facebook.com/{s['whatsapp_api_version']}/{s['whatsapp_waba_id']}/message_templates?fields=name,status,category,language,components&limit=100"
    items=[]
    try:
        while url:
            request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
            with urllib.request.urlopen(request,timeout=20) as response:result=json.load(response)
            items.extend(result.get('data',[]))
            next_url=result.get('paging',{}).get('next','')
            # Paging URLs can contain access tokens. Keep them in runtime memory only.
            from urllib.parse import urlparse
            if next_url and (urlparse(next_url).scheme!='https' or urlparse(next_url).hostname!='graph.facebook.com'):raise ValueError('Unexpected Meta paging address.')
            url=next_url
            if len(items)>1000:raise ValueError('Template catalogue is too large for this release.')
    except (urllib.error.URLError,TimeoutError,OSError,json.JSONDecodeError):raise ValueError('Unable to refresh templates. Check Meta account permissions, token and connectivity.') from None
    with shop.lock,shop.connect() as db:
        db.execute('DELETE FROM whatsapp_templates')
        for item in items:
            body,supported=supported_template(item.get('components',[]))
            header=next((c.get('format','') for c in item.get('components',[]) if c.get('type')=='HEADER'),'')
            count=len(set(re.findall(r'\{\{(\d+)\}\}',body)))
            db.execute('INSERT INTO whatsapp_templates(name,language,status,category,body,supported,checked,header_format,parameter_count,components) VALUES(?,?,?,?,?,?,?,?,?,?)',(item['name'],item['language'],item['status'],item.get('category',''),body,int(supported),dt.datetime.now(dt.timezone.utc).isoformat(),header,count,json.dumps(item.get('components',[]))))
    return {'count':len(items)}


def eligible(db,ids):
    recipients=[];seen=set()
    for ident in ids:
        p=db.execute("SELECT * FROM parties WHERE id=? AND kind='customer'",(int(ident),)).fetchone()
        if not p or not p['whatsapp_marketing_opt_in']:continue
        try:phone=whatsapp_number(p['phone'])
        except ValueError:continue
        if phone in seen:continue
        seen.add(phone);recipients.append({'id':p['id'],'name':p['name'],'phone':phone})
    return recipients


def act(shop,action,data):
    if action=='whatsapp_templates':return refresh_templates(shop)
    if action=='whatsapp_webhook':
        save_webhook(shop.folder,data)
        return {'configured':True}
    with shop.lock,shop.connect() as db:
        if action=='campaign_create':
            name=str(data.get('name','')).strip();offer=str(data.get('offer','')).strip()
            if not name or len(name)>100 or not offer or len(offer)>800:raise ValueError('Enter a campaign name (up to 100 characters) and offer (up to 800).')
            template=str(data.get('template',''));language=str(data.get('language',''))
            t=db.execute('SELECT * FROM whatsapp_templates WHERE name=? AND language=?',(template,language)).fetchone()
            if not t or t['category']!='MARKETING' or not t['supported']:
                raise ValueError('Refresh templates and select a supported marketing template.')
            asset=str(data.get('asset_id',''))
            if t['header_format']=='IMAGE' and not db.execute('SELECT 1 FROM media_assets WHERE id=?',(asset,)).fetchone():raise ValueError('Choose an uploaded campaign image.')
            if t['header_format']!='IMAGE':asset=''
            ids=data.get('customer_ids',[])
            if not isinstance(ids,list) or not ids or len(ids)>1000:raise ValueError('Select between 1 and 1000 customers.')
            recipients=eligible(db,ids)
            if not recipients:raise ValueError('No selected customers have promotional WhatsApp consent and a valid mobile number.')
            scheduled=str(data.get('scheduled','')).strip()
            if scheduled:
                try:when=dt.datetime.fromisoformat(scheduled)
                except ValueError:raise ValueError('Enter a valid scheduled date and time.') from None
                if when.tzinfo is None:raise ValueError('Scheduled time must include a timezone.')
                if when<=dt.datetime.now(dt.timezone.utc):raise ValueError('Schedule a future time, or leave it blank to send after approval.')
                scheduled=when.isoformat()
            ident=secrets.token_hex(16)
            db.execute('INSERT INTO whatsapp_campaigns(id,name,created,template,language,offer,recipients,scheduled,asset_id) VALUES(?,?,?,?,?,?,?,?,?)',(ident,name,dt.datetime.now(dt.timezone.utc).isoformat(),template,language,offer,json.dumps(recipients),scheduled,asset))
            shop.audit(db,action,{'id':ident,'count':len(recipients)})
            return {'id':ident,'recipient_count':len(recipients)}
        row=db.execute('SELECT * FROM whatsapp_campaigns WHERE id=?',(str(data.get('id','')),)).fetchone()
        if not row:raise ValueError('Campaign not found.')
        if action=='campaign_cancel':
            db.execute("UPDATE whatsapp_campaigns SET status='cancelled' WHERE id=?",(row['id'],))
            db.execute("UPDATE notifications SET status='cancelled',detail='Campaign cancelled by owner.' WHERE campaign_id=? AND status IN ('queued','retry')",(row['id'],))
            shop.audit(db,action,{'id':row['id']})
            return {'cancelled':True}
        if action!='campaign_approve' or row['status']!='draft':raise ValueError('Only a draft campaign can be approved once.')
        if data.get('confirmed') is not True:raise ValueError('Review the audience and message, then confirm this campaign.')
        t=db.execute('SELECT * FROM whatsapp_templates WHERE name=? AND language=?',(row['template'],row['language'])).fetchone()
        if not t or t['status']!='APPROVED' or not t['supported'] or t['category']!='MARKETING':raise ValueError('The marketing template is not currently approved.')
        if dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(t['checked'])>dt.timedelta(hours=24):raise ValueError('Refresh templates before approving this campaign.')
        s=shop.settings(db)
        if not s['whatsapp_enabled'] or not read_token(shop.folder):raise ValueError('Configure and enable a notification sender before approving a campaign.')
        from media_catalogue import meta_image
        image_id=meta_image(shop,row['asset_id'],db) if t['header_format']=='IMAGE' else ''
        count=0
        for recipient in json.loads(row['recipients']):
            current=eligible(db,[recipient['id']])
            if not current or current[0]['phone']!=recipient['phone']:continue
            ident='campaign:'+row['id']+':'+recipient['phone']
            shop.notification(db,ident,'marketing',recipient['phone'],row['template'],[current[0]['name'],s['name'],row['offer']] if t['parameter_count'] else [],party_id=recipient['id'])
            db.execute('UPDATE notifications SET campaign_id=?,language=?,image_id=?,next_attempt=? WHERE id=?',(row['id'],row['language'],image_id,row['scheduled'] or dt.datetime.now(dt.timezone.utc).isoformat(),ident));count+=1
        if not count:raise ValueError('All previewed recipients opted out or changed their mobile number. Create a fresh campaign.')
        db.execute("UPDATE whatsapp_campaigns SET status='approved',approved=? WHERE id=?",(dt.datetime.now(dt.timezone.utc).isoformat(),row['id']))
        shop.audit(db,action,{'id':row['id'],'count':count})
        return {'queued':count}


def challenge(shop,query):
    config=read_webhook(shop.folder)
    mode=query.get('hub.mode',[''])[0];token=query.get('hub.verify_token',[''])[0]
    if mode!='subscribe' or not config or not hmac.compare_digest(token,config['verify_token']):raise PermissionError('Webhook verification failed.')
    return query.get('hub.challenge',[''])[0]


RANK={'sent':1,'delivered':2,'read':3,'failed':0}
def receive(shop,raw,signature):
    config=read_webhook(shop.folder)
    expected='sha256='+hmac.new(config.get('app_secret','').encode(),raw,hashlib.sha256).hexdigest()
    if not config or not hmac.compare_digest(signature,expected):raise PermissionError('Invalid webhook signature.')
    payload=json.loads(raw)
    if payload.get('object')!='whatsapp_business_account':raise ValueError('Unexpected webhook object.')
    with shop.lock,shop.connect() as db:
        settings=shop.settings(db);before=None
        for entry in payload.get('entry',[]):
            if str(entry.get('id'))!=settings.get('whatsapp_waba_id'):continue
            for change in entry.get('changes',[]):
                value=change.get('value',{})
                if change.get('field')!='messages' or str(value.get('metadata',{}).get('phone_number_id'))!=settings['whatsapp_phone_id']:continue
                for status in value.get('statuses',[]):
                    ident=str(status.get('id',''));state=status.get('status');stamp=int(status.get('timestamp',0))
                    if not ident or state not in RANK:continue
                    old=db.execute('SELECT * FROM whatsapp_receipts WHERE provider_id=?',(ident,)).fetchone()
                    if old:
                        if old['status'] in ('delivered','read') and RANK[state]<RANK[old['status']]:continue
                        if old['timestamp']>=stamp and RANK[state]<=RANK[old['status']]:continue
                    db.execute('INSERT OR REPLACE INTO whatsapp_receipts VALUES(?,?,?)',(ident,state,stamp))
                    apply_receipt(db,ident)
                for message in value.get('messages',[]):
                    text=message.get('text',{}).get('body','') if message.get('type')=='text' else message.get('button',{}).get('text','')
                    if str(text).strip().upper() not in ('STOP','UNSUBSCRIBE','CANCEL','OPT OUT'):continue
                    mid=str(message.get('id',''))
                    if not mid or db.execute('SELECT 1 FROM whatsapp_inbound WHERE id=?',(mid,)).fetchone():continue
                    phone=whatsapp_number(message.get('from',''))
                    before=before or shop.capture(db)
                    for p in db.execute("SELECT * FROM parties WHERE kind='customer'").fetchall():
                        try:same=whatsapp_number(p['phone'])==phone
                        except ValueError:same=False
                        if same:db.execute('UPDATE parties SET whatsapp_opt_in=0,whatsapp_marketing_opt_in=0 WHERE id=?',(p['id'],))
                    db.execute("UPDATE notifications SET status='cancelled',detail='Recipient requested STOP.' WHERE phone=? AND status IN ('queued','retry')",(phone,))
                    db.execute("UPDATE internal_contacts SET opt_in=0 WHERE phone=?",(phone,))
                    db.execute('INSERT INTO whatsapp_inbound VALUES(?,?)',(mid,dt.datetime.now(dt.timezone.utc).isoformat()))
                    shop.audit(db,'whatsapp_opt_out',{'phone':phone})
        if before:shop.record_event(db,before)
    return {'received':True}


def apply_receipt(db,ident):
    receipt=db.execute('SELECT * FROM whatsapp_receipts WHERE provider_id=?',(ident,)).fetchone()
    if receipt:
        db.execute('UPDATE notifications SET status=?,detail=? WHERE provider_id=?',(receipt['status'],'Meta reported '+receipt['status']+'.',ident))
