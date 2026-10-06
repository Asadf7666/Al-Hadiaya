"""WhatsApp template outbox. Uses stdlib; keeps API credentials out of database/sync."""
import ctypes
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

def whatsapp_number(value):
    digits = re.sub(r'\D','',str(value or ''))
    if len(digits)==10:
        digits='91'+digits
    if digits.startswith('00'):
        digits=digits[2:]
    if not re.fullmatch(r'[1-9][0-9]{7,14}',digits):
        raise ValueError('WhatsApp needs a valid mobile number with country code (Indian 10-digit mobiles default to +91).')
    return digits

def protect(raw, decrypt=False):
    if os.name!='nt':
        return raw
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    buf=(ctypes.c_ubyte*len(raw)).from_buffer_copy(raw)
    source=Blob(len(raw),buf);target=Blob()
    fn=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise OSError('Windows credential protection failed.')
    try:
        return ctypes.string_at(target.pbData,target.cbData)
    finally:
        free=ctypes.windll.kernel32.LocalFree
        free.argtypes=[ctypes.c_void_p]
        free.restype=ctypes.c_void_p
        free(target.pbData)

def token_file(folder):
    return Path(folder)/'whatsapp-credential.bin'

def save_token(folder, value):
    path=token_file(folder)
    if not str(value).strip():
        path.unlink(missing_ok=True)
        return
    temporary=path.with_suffix('.tmp')
    temporary.touch(mode=0o600,exist_ok=True)
    temporary.write_bytes(protect(str(value).strip().encode()))
    temporary.replace(path)
    if os.name!='nt':
        path.chmod(0o600)

def read_token(folder):
    path=token_file(folder)
    return protect(path.read_bytes(),decrypt=True).decode() if path.exists() else ''

def deliver(settings, token, row):
    version=settings['whatsapp_api_version']
    phone_id=settings['whatsapp_phone_id']
    if not re.fullmatch(r'v[0-9]+\.[0-9]+',version) or not re.fullmatch(r'[0-9]+',phone_id):
        raise ValueError('Configure the Graph API version and WhatsApp sender phone-number ID.')
    payload={'messaging_product':'whatsapp','recipient_type':'individual','to':row['phone'],'type':'template',
             'template':{'name':row['template'],'language':{'code':row.get('language') or settings['whatsapp_language']},
             'components':[]}}
    if row.get('image_id'):
        payload['template']['components'].append({'type':'header','parameters':[{'type':'image','image':{'id':row['image_id']}}]})
    params=json.loads(row['parameters'])
    if params:payload['template']['components'].append({'type':'body','parameters':[{'type':'text','text':str(v)} for v in params]})
    if not payload['template']['components']:payload['template'].pop('components')
    if row.get('message_type')=='session':
        content=json.loads(row['payload'])
        if content.get('type') not in ('text','interactive'):raise ValueError('Unsupported service message.')
        payload={'messaging_product':'whatsapp','recipient_type':'individual','to':row['phone'],**content}
    req=urllib.request.Request(f'https://graph.facebook.com/{version}/{phone_id}/messages',
        data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            result=json.load(response)
        message_id=result.get('messages',[{}])[0].get('id')
        if not message_id:
            return 'uncertain','No message ID was returned. Check Meta before sending again.',''
        return 'accepted','Accepted by WhatsApp API; delivery/read status requires later webhook integration.',message_id
    except urllib.error.HTTPError as e:
        # Extract numeric error codes only, never raw responses or credentials.
        try:code=json.load(e).get('error',{}).get('code')
        except Exception:code=None
        reason={132001:'Template is not approved/available in the selected language.',131047:'The 24-hour service window has expired; an approved template is required.',131009:'Catalogue/product setup or message parameters are invalid.',131026:'Recipient cannot receive this WhatsApp message.',131049:'Meta restricted marketing delivery to this recipient.'}.get(code,'Check sender setup, template and permissions.')
        return ('retry' if e.code==429 or e.code>=500 else 'failed'),f'WhatsApp HTTP {e.code}, code {code}: {reason}',''
    except (TimeoutError,urllib.error.URLError,OSError,json.JSONDecodeError):
        return 'uncertain','The response was lost or unavailable. Check Meta before retrying to avoid duplicate notifications.',''

def process_outbox(shop):
    with shop.lock,shop.connect() as db:
        settings=shop.settings(db)
        if not settings['whatsapp_enabled']:
            return {'processed':0}
        token=read_token(shop.folder)
        if not token:
            return {'processed':0,'message':'WhatsApp token is not configured.'}
        current=dt.datetime.now().astimezone().isoformat()
        rows=[dict(r) for r in db.execute("SELECT * FROM notifications WHERE status IN ('queued','retry','blocked') AND julianday(next_attempt)<=julianday(?) ORDER BY created LIMIT 10",(current,))]
        # Claim before network I/O. A crash cannot automatically resubmit a possibly sent message.
        for row in rows:
            db.execute("UPDATE notifications SET status='sending',attempts=attempts+1 WHERE id=?",(row['id'],))
    for row in rows:
        try:
            with shop.lock,shop.connect() as db:
                if row['internal_id'] is not None:
                    p=db.execute('SELECT * FROM internal_contacts WHERE id=?',(row['internal_id'],)).fetchone()
                    consent=p and p['opt_in']
                elif row['kind'] in ('order','catalogue'):
                    from whatsapp_orders import window
                    session=db.execute('SELECT * FROM whatsapp_sessions WHERE phone=?',(row['phone'],)).fetchone()
                    order=db.execute('SELECT * FROM trade_orders WHERE id=?',(row.get('order_id',''),)).fetchone()
                    p={'phone':row['phone']}
                    consent=bool(session and not session['stopped'] and (order['contact_allowed'] if order else window(db,row['phone'])))
                else:
                    p=db.execute('SELECT * FROM parties WHERE id=?',(row['party_id'],)).fetchone()
                    consent=p and p['whatsapp_marketing_opt_in' if row['kind']=='marketing' else 'whatsapp_opt_in']
                if row.get('campaign_id'):
                    campaign=db.execute('SELECT status FROM whatsapp_campaigns WHERE id=?',(row['campaign_id'],)).fetchone()
                    consent=consent and campaign and campaign['status']=='approved'
                current_row=db.execute('SELECT status FROM notifications WHERE id=?',(row['id'],)).fetchone()
                consent=consent and current_row and current_row['status']=='sending'
                if not consent or whatsapp_number(p['phone'])!=row['phone']:
                    db.execute("UPDATE notifications SET status='cancelled',detail='Recipient opted out or changed mobile number.' WHERE id=?",(row['id'],))
                    continue
                from whatsapp_orders import window
                if row['internal_id'] is not None and window(db,row['phone']):
                    params=json.loads(row['parameters'])
                    row['message_type']='session';row['payload']=json.dumps({'type':'text','text':{'body':'*'+str(params[0])+'*\n_Internal update: '+str(params[1])+'_\n\n'+str(params[2])}})
                if row.get('message_type')=='session' and not window(db,row['phone']):
                    if not row.get('order_id'):
                        db.execute("UPDATE notifications SET status='cancelled',detail='Service window expired. Customer must send a new message.' WHERE id=?",(row['id'],));continue
                    row['message_type']='template'
                if row.get('message_type','template')=='template':
                    template=db.execute('SELECT status FROM whatsapp_templates WHERE name=? AND language=?',(row['template'],row.get('language') or settings['whatsapp_language'])).fetchone()
                    if template and template['status']!='APPROVED':
                        wait=(dt.datetime.now().astimezone()+dt.timedelta(minutes=5)).isoformat()
                        db.execute("UPDATE notifications SET status='blocked',detail=?,attempts=attempts-1,next_attempt=? WHERE id=?",('Waiting for Meta template approval: '+row['template'],wait,row['id']));continue
            status,detail,message_id=deliver(settings,token,row)
        except Exception:
            status,detail,message_id='failed','Check notification configuration. No automatic retry was scheduled.',''
        delay=min(3600,60*2**min(row['attempts'],5))
        if status=='retry' and row['attempts']>=4:
            status='failed';detail+=' Retry limit reached.'
        retry=(dt.datetime.now().astimezone()+dt.timedelta(seconds=delay)).isoformat(timespec='seconds')
        with shop.lock,shop.connect() as db:
            db.execute('UPDATE notifications SET status=?,detail=?,provider_id=?,next_attempt=? WHERE id=?',(status,detail,message_id,retry,row['id']))
            if message_id:
                from outreach import apply_receipt
                apply_receipt(db,message_id)
    return {'processed':len(rows)}
