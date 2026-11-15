"""Offline licensing: signed licence file, 60-day trial, read-only once lapsed.

One licence unlocks one PC. Verification is Ed25519 (RFC 8032) with the Python
standard library only, so no internet and no extra packages are needed.
Business records stay viewable and exportable in every state.
"""
import base64,datetime as dt,hashlib,hmac,json,os,re,threading,time
from pathlib import Path

PRODUCT='al-hadiya-traders'
PUBLIC_KEY='76066e9cb0498bb685e773002c87de2e3c101716039b0b159b8974a079328561'
TRIAL_DAYS=60
# Licences withdrawn after issue. A replacement carries a new id.
REVOKED={'AHT-OWNER-0001','AHT-2026-0001'}
# Release date of this build. A licence with a support period covers builds released within it.
BUILD_DATE='2026-11-15'
# Licence types. Each can be dated or perpetual and may carry a support period and a feature list.
TYPES={'single':'Single PC','first':'First PC installed','site':'Site (any PC)','trial':'Evaluation'}
# Optional modules a licence can leave out. A licence without a feature list includes everything.
FEATURES={'sync':'Sync between PCs','whatsapp':'WhatsApp updates and orders'}
ACTIVATION_DAYS=30
GRACE_DAYS=7
WARN_DAYS=14
DAY=86400
ROLLBACK_TOLERANCE=2*DAY
BEGIN='-----BEGIN AL HADIYA LICENCE-----'
END='-----END AL HADIYA LICENCE-----'
# Actions that stay available without a valid licence: nothing here writes business records.
ALWAYS_ALLOWED={'logout','shutdown','backup','print_receipt','print_shift','print_test','licence_install','licence_remove','staff_user','staff_password','staff_disable','staff_enable'}
_SEAL=b'al-hadiya-traders/trial-record/v1'

# ---- Ed25519 (RFC 8032) -----------------------------------------------------
_P=2**255-19
_L=2**252+27742317777372353535851937790883648493
_D=-121665*pow(121666,-1,_P)%_P
_I=pow(2,(_P-1)//4,_P)
_BY=4*pow(5,-1,_P)%_P

def _recover_x(y,sign):
    if y>=_P:return None
    x2=(y*y-1)*pow(_D*y*y+1,-1,_P)%_P
    if x2==0:return None if sign else 0
    x=pow(x2,(_P+3)//8,_P)
    if (x*x-x2)%_P:x=x*_I%_P
    if (x*x-x2)%_P:return None
    return _P-x if (x&1)!=sign else x

_BX=_recover_x(_BY,0)
_B=(_BX,_BY,1,_BX*_BY%_P)

def _add(a,b):
    A=(a[1]-a[0])*(b[1]-b[0])%_P;B=(a[1]+a[0])*(b[1]+b[0])%_P
    C=2*a[3]*b[3]*_D%_P;Dd=2*a[2]*b[2]%_P
    E=B-A;F=Dd-C;G=Dd+C;H=B+A
    return (E*F%_P,G*H%_P,F*G%_P,E*H%_P)

def _mul(s,point):
    result=(0,1,1,0)
    while s>0:
        if s&1:result=_add(result,point)
        point=_add(point,point);s>>=1
    return result

def _same(a,b):
    return not (a[0]*b[2]-b[0]*a[2])%_P and not (a[1]*b[2]-b[1]*a[2])%_P

def _encode(point):
    z=pow(point[2],-1,_P);x=point[0]*z%_P;y=point[1]*z%_P
    return (y|((x&1)<<255)).to_bytes(32,'little')

def _decode(raw):
    if len(raw)!=32:return None
    y=int.from_bytes(raw,'little');sign=y>>255;y&=(1<<255)-1
    x=_recover_x(y,sign)
    return None if x is None else (x,y,1,x*y%_P)

def _hint(*parts):
    return int.from_bytes(hashlib.sha512(b''.join(parts)).digest(),'little')%_L

def _expand(seed):
    if len(seed)!=32:raise ValueError('A signing key is 32 bytes.')
    h=hashlib.sha512(seed).digest()
    a=int.from_bytes(h[:32],'little');a&=(1<<254)-8;a|=1<<254
    return a,h[32:]

def public_key(seed):
    return _encode(_mul(_expand(seed)[0],_B))

def sign(seed,message):
    """Vendor side only: needs the private signing key, which never ships."""
    a,prefix=_expand(seed);A=_encode(_mul(a,_B))
    r=_hint(prefix,message);R=_encode(_mul(r,_B))
    return R+((r+_hint(R,A,message)*a)%_L).to_bytes(32,'little')

def verify(public,message,signature):
    if len(public)!=32 or len(signature)!=64:return False
    A=_decode(public);R=_decode(signature[:32]);s=int.from_bytes(signature[32:],'little')
    if A is None or R is None or s>=_L:return False
    return _same(_mul(s,_B),_add(R,_mul(_hint(signature[:32],public,message),A)))

# ---- licence file -----------------------------------------------------------
def _b64(raw):return base64.urlsafe_b64encode(raw).decode().rstrip('=')
def _unb64(text):return base64.urlsafe_b64decode(text+'='*(-len(text)%4))

def machine_id():
    """Stable per-PC installation ID shown to the owner and bound into the licence."""
    raw=''
    if os.name=='nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
                raw=str(winreg.QueryValueEx(key,'MachineGuid')[0])
        except OSError:pass
    else:
        for name in ('/etc/machine-id','/var/lib/dbus/machine-id'):
            try:raw=Path(name).read_text().strip()
            except OSError:continue
            if raw:break
    if not raw:
        import platform,uuid
        raw=platform.node()+':'+hex(uuid.getnode())
    digest=hashlib.sha256((PRODUCT+'|'+raw.lower()).encode()).hexdigest()[:16].upper()
    return '-'.join(digest[i:i+4] for i in range(0,16,4))

def normalise_machine(value):
    value=re.sub(r'[^0-9A-Fa-f*]','',str(value or '')).upper()
    if value=='*':return '*'
    if len(value)!=16:raise ValueError('An installation ID has 16 characters, such as 1A2B-3C4D-5E6F-7A8B.')
    return '-'.join(value[i:i+4] for i in range(0,16,4))

def pack(payload,seed):
    """Vendor side: serialise and sign a licence payload into the text of a .lic file."""
    body=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
    text=_b64(body)+'.'+_b64(sign(seed,body))
    return '\n'.join([BEGIN,*(text[i:i+64] for i in range(0,len(text),64)),END])+'\n'

def _date(value,label):
    try:return dt.date.fromisoformat(str(value))
    except ValueError:raise ValueError(f'The licence {label} date is unreadable.')

def parse(text):
    """Return the verified payload of a licence file, or raise ValueError saying why not."""
    if not isinstance(text,str) or len(text)>20000:raise ValueError('This is not a licence file.')
    body=''.join(line.strip() for line in text.replace(BEGIN,'\n').replace(END,'\n').splitlines())
    if body.count('.')!=1 or re.search(r'[^A-Za-z0-9_.\-]',body):raise ValueError('This is not a licence file.')
    try:
        raw,signature=(_unb64(part) for part in body.split('.'))
    except ValueError:raise ValueError('This is not a licence file.')
    if not verify(bytes.fromhex(PUBLIC_KEY),raw,signature):
        raise ValueError('The licence signature is not valid. Use the file exactly as issued.')
    try:
        payload=json.loads(raw)
    except ValueError:raise ValueError('The licence contents are unreadable.')
    if not isinstance(payload,dict) or payload.get('product')!=PRODUCT or payload.get('v') not in (1,2):
        raise ValueError('This licence is for a different product.')
    _date(payload.get('issued'),'issue')
    if payload.get('expires') is not None:_date(payload['expires'],'expiry')
    payload['machine']=normalise_machine(payload.get('machine'))
    # Version 1 files had no type: bound to a PC or not.
    kind=payload.setdefault('type','site' if payload['machine']=='*' else 'single')
    if kind not in TYPES or (kind=='single')!=(payload['machine']!='*'):raise ValueError('The licence type is not recognised by this version.')
    if kind=='trial' and payload.get('expires') is None:raise ValueError('An evaluation licence must have an end date.')
    for key,label in (('activate_by','activation'),('support_until','support')):
        if payload.get(key) is not None:payload[key]=_date(payload[key],label).isoformat()
    if kind=='first' and not payload.get('activate_by'):raise ValueError('The licence contents are incomplete.')
    features=payload.get('features')
    if features is not None and (not isinstance(features,list) or any(f not in FEATURES for f in features)):raise ValueError('The licence lists a feature this version does not know.')
    if payload.get('id') in REVOKED:raise ValueError('This licence was withdrawn. Install the replacement you were sent.')
    for key in ('id','customer'):
        if not isinstance(payload.get(key),str) or not payload[key].strip():raise ValueError('The licence contents are incomplete.')
    return payload

# ---- per-installation state --------------------------------------------------
class Licence:
    """Trial clock, installed licence and the resulting status for one installation."""
    def __init__(self,folder,registry=False,machine=None,clock=time.time):
        self.folder=Path(folder)/'licence';self.folder.mkdir(parents=True,exist_ok=True)
        self.record=self.folder/'state.json';self.file=self.folder/'licence.lic'
        self.registry=bool(registry and os.name=='nt');self.machine=machine or machine_id()
        self.clock=clock;self.lock=threading.RLock();self.cache=None
        with self.lock:self._load()

    # The trial record is sealed so a casual edit is noticed, and mirrored in the
    # registry so removing the data folder does not start a new trial.
    def _seal(self,first,last):
        return hmac.new(_SEAL,f'{first}:{last}'.encode(),hashlib.sha256).hexdigest()
    def _read_file(self):
        try:
            data=json.loads(self.record.read_text())
            first,last=int(data['first_run']),int(data['last_seen'])
            return (first,last) if hmac.compare_digest(data.get('seal',''),self._seal(first,last)) else 'damaged'
        except FileNotFoundError:return None
        except (OSError,ValueError,KeyError,TypeError):return 'damaged'
    def _read_registry(self):
        if not self.registry:return None
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\AlHadiyaTraders\Licence') as key:
                first,last,seal=(winreg.QueryValueEx(key,name)[0] for name in ('FirstRun','LastSeen','Seal'))
            first,last=int(first),int(last)
            return (first,last) if hmac.compare_digest(str(seal),self._seal(first,last)) else 'damaged'
        except (OSError,ValueError,TypeError):return None
    def _write(self):
        seal=self._seal(self.first,self.last)
        temp=self.record.with_suffix('.tmp')
        temp.write_text(json.dumps({'first_run':self.first,'last_seen':self.last,'seal':seal}));os.replace(temp,self.record)
        if self.registry:
            try:
                import winreg
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\AlHadiyaTraders\Licence') as key:
                    for name,value in (('FirstRun',str(self.first)),('LastSeen',str(self.last)),('Seal',seal)):
                        winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
            except OSError:pass
    def _load(self):
        now=int(self.clock());sources=[self._read_file(),self._read_registry()]
        good=[s for s in sources if isinstance(s,tuple)]
        if good:
            # The earliest first run and the latest sighting win, whichever copy held them.
            self.first=min(s[0] for s in good);self.last=max(s[1] for s in good)
        elif 'damaged' in sources:
            self.first=now-TRIAL_DAYS*DAY-1;self.last=now
        else:
            self.first=now;self.last=now
        try:self._write()
        except OSError:pass
    def now(self):
        """Wall clock, never earlier than the latest time this installation has seen."""
        now=int(self.clock())
        with self.lock:
            if now>self.last+600:
                self.last=now
                try:self._write()
                except OSError:pass
            return max(now,self.last) if now<self.last-ROLLBACK_TOLERANCE else now

    # A first-PC licence is tied to the PC it is first installed on. The tie is a sealed
    # record kept beside the trial clock (and in the registry), so a copied data folder
    # does not carry the licence to another PC, and the file cannot start a new
    # installation after its activation date.
    def _activation_seal(self,ident,machine,when):
        return hmac.new(_SEAL,f'activation:{ident}:{machine}:{when}'.encode(),hashlib.sha256).hexdigest()
    def _activations(self):
        found=[]
        try:found.append(json.loads((self.folder/'activation.json').read_text()))
        except (OSError,ValueError):pass
        if self.registry:
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\AlHadiyaTraders\Licence') as key:found.append(json.loads(winreg.QueryValueEx(key,'Activation')[0]))
            except (OSError,ValueError,TypeError):pass
        return [a for a in found if isinstance(a,dict) and all(isinstance(a.get(k),t) for k,t in (('id',str),('machine',str),('when',int),('seal',str)))
                and hmac.compare_digest(a['seal'],self._activation_seal(a['id'],a['machine'],a['when']))]
    def _activated(self,ident):
        """'here', 'elsewhere' or None for a first-PC licence id."""
        records=[a for a in self._activations() if a['id']==ident]
        return None if not records else 'here' if all(a['machine']==self.machine for a in records) else 'elsewhere'
    def _activate(self,ident):
        when=int(self.clock());record={'id':ident,'machine':self.machine,'when':when,'seal':self._activation_seal(ident,self.machine,when)}
        temp=self.folder/'activation.tmp';temp.write_text(json.dumps(record));os.replace(temp,self.folder/'activation.json')
        if self.registry:
            try:
                import winreg
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\AlHadiyaTraders\Licence') as key:winreg.SetValueEx(key,'Activation',0,winreg.REG_SZ,json.dumps(record))
            except OSError:pass
    def _fits(self,payload):
        """Why this licence cannot run on this PC with this build, or '' when it can."""
        if payload['type']=='single' and payload['machine']!=self.machine:
            return f'This licence was issued for installation {payload["machine"]}. This PC is {self.machine}.'
        if payload.get('support_until') and payload['support_until']<BUILD_DATE:
            return f'This licence covers versions released up to {payload["support_until"]}. Renew support to use this version.'
        return ''

    def install(self,text):
        payload=parse(text)
        problem=self._fits(payload)
        if problem:raise ValueError(problem)
        with self.lock:
            if (self._days_left(payload,self.now()) or 0)<-GRACE_DAYS:raise ValueError(f'This licence expired on {payload["expires"]}. Ask for a renewal.')
            if payload['type']=='first':
                state=self._activated(payload['id'])
                if state=='elsewhere':raise ValueError('This licence is already tied to another PC. Ask your supplier for a licence for this PC.')
                if state is None:
                    today=dt.date.fromtimestamp(self.now()).isoformat()
                    if today>payload['activate_by']:raise ValueError(f'This licence had to be installed by {payload["activate_by"]}. Ask your supplier for a fresh file.')
                    self._activate(payload['id'])
            temp=self.file.with_suffix('.tmp');temp.write_text(text.strip()+'\n',encoding='utf-8');os.replace(temp,self.file)
            self.cache=None
        return self.status()
    def remove(self):
        with self.lock:
            self.file.unlink(missing_ok=True);self.cache=None
        return self.status()

    @staticmethod
    def _days_left(payload,now):
        if payload.get('expires') is None:return None
        end=dt.datetime.combine(_date(payload['expires'],'expiry'),dt.time(23,59,59)).timestamp()
        return int((end-now)//DAY)
    def status(self):
        with self.lock:
            now=self.now()
            if self.cache and self.cache[0]==now//60:return dict(self.cache[1])
            result=self._status(now);self.cache=(now//60,result)
            return dict(result)
    def _status(self,now):
        trial_left=max(0,TRIAL_DAYS-max(0,now-self.first)//DAY)
        base={'installation_id':self.machine,'trial_days':TRIAL_DAYS,'trial_days_left':int(trial_left),'grace_days':GRACE_DAYS,
              'licence_id':'','customer':'','edition':'','issued':'','expires':'','days_left':None,'problem':'',
              'type':'','type_label':'','bound_to':'','support_until':'','features':None,'feature_labels':FEATURES}
        payload=None
        if self.file.exists():
            try:
                payload=parse(self.file.read_text(encoding='utf-8'))
                problem=self._fits(payload)
                if not problem and payload['type']=='first':
                    state=self._activated(payload['id'])
                    problem='' if state=='here' else 'The installed licence is tied to another PC.' if state=='elsewhere' else 'Install the licence from this screen to tie it to this PC.'
                if problem:
                    payload=None;base['problem']='The installed licence belongs to another PC.' if 'issued for installation' in problem else problem
            except (ValueError,OSError) as error:
                base['problem']=str(error)
        if payload:
            left=self._days_left(payload,now)
            base.update(licence_id=payload['id'],customer=payload['customer'],edition=str(payload.get('edition') or 'Standard'),
                        issued=payload['issued'],expires=payload['expires'] or '',days_left=left,type=payload['type'],type_label=TYPES[payload['type']],
                        bound_to='Any PC of this business' if payload['type'] in ('site','trial') else 'This PC ('+self.machine+')',
                        support_until=payload.get('support_until') or '',features=payload.get('features'))
            if left is None or left>=0:
                return {**base,'status':'licensed','writable':True,'warn':left is not None and left<=WARN_DAYS,
                        'message':'Licensed to '+payload['customer']+('.' if left is None else f' until {payload["expires"]}.')}
            if left>=-GRACE_DAYS:
                return {**base,'status':'grace','writable':True,'warn':True,
                        'message':f'Licence expired on {payload["expires"]}. {GRACE_DAYS+left+1} day(s) of grace remain before the app becomes read-only.'}
            return {**base,'status':'expired','writable':False,'warn':True,
                    'message':f'Licence expired on {payload["expires"]}. Records are read-only until a renewal is installed.'}
        if trial_left>0:
            return {**base,'status':'trial','writable':True,'warn':trial_left<=WARN_DAYS or bool(base['problem']),
                    'message':f'Trial: {int(trial_left)} of {TRIAL_DAYS} days remain.'}
        return {**base,'status':'unlicensed','writable':False,'warn':True,
                'message':'The trial has ended. Records are read-only until a licence is installed.'}
    def require(self,action):
        """Raise when a lapsed licence must block a business write."""
        if action in ALWAYS_ALLOWED:return
        status=self.status()
        if not status['writable']:raise LicenceRequired(status['message'])
        feature=feature_of(action)
        if feature and not self.allows(feature,status):raise LicenceRequired(FEATURES[feature]+' is not included in this licence.')
    def allows(self,feature,status=None):
        """Whether an optional module is available. Everything is included during the trial."""
        status=status or self.status()
        return status['features'] is None or feature in status['features']

def feature_of(action):
    """The optional module an action belongs to, if any."""
    if action=='sync' or action.startswith('cloud_'):return 'sync'
    if action.startswith(('whatsapp','campaign','commerce')) or action in ('internal_contact','trade_order_status','trade_order_reprice'):return 'whatsapp'
    return None

class LicenceRequired(Exception):
    pass
