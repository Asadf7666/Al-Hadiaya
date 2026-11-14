"""Installer and recovery tasks built into the Windows program.

  AlHidayaTraders.exe --maintenance            close the running app and back up before an update
  AlHidayaTraders.exe --reset-owner USERNAME   set a new password for a local owner account
"""
import json,os,socket,sys,time,urllib.request

PORT=8765

def running():
    with socket.socket() as s:
        s.settimeout(.5)
        return s.connect_ex(('127.0.0.1',PORT))==0

def prepare_update():
    """Close the local app cleanly and back up its data. Returns a process exit code."""
    from app import Shop,DATA
    try:
        if running():
            # Ignore system proxies for strictly local installer communication.
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            from notifications import protect
            control=DATA/'maintenance-credential.bin'
            if control.exists():token=protect(control.read_bytes(),decrypt=True).decode()
            else:
                with opener.open(f'http://127.0.0.1:{PORT}/api/session',timeout=3) as r:token=json.load(r)['token']
            request=urllib.request.Request(f'http://127.0.0.1:{PORT}/api/shutdown',data=b'{}',headers={'X-Shop-Token':token,'Content-Type':'application/json'})
            with opener.open(request,timeout=10) as r:json.load(r)
            for _ in range(40):
                if not running():break
                time.sleep(.25)
            if running():raise RuntimeError('App did not close. Close it and run the installer again.')
            time.sleep(1)
        if (DATA/'shop.sqlite3').exists():Shop().backup(local_only=True)
        return 0
    except Exception as error:
        if sys.stderr:print(str(error),file=sys.stderr)
        return 1

def _console():
    """The Windows program has no console of its own; open one for the password prompt."""
    if os.name!='nt':return
    import ctypes
    ctypes.windll.kernel32.AllocConsole()
    sys.stdout=sys.stderr=open('CONOUT$','w',encoding='utf-8')

def _say(text):
    if sys.stdout:print(text,flush=True)

def _secret(prompt):
    if os.name!='nt':
        import getpass
        return getpass.getpass(prompt)
    import msvcrt
    for c in prompt:msvcrt.putwch(c)
    typed=[]
    while True:
        c=msvcrt.getwch()
        if c in '\r\n':break
        if c=='\x03':raise KeyboardInterrupt
        if c in '\x00\xe0':msvcrt.getwch();continue
        if c=='\b':typed=typed[:-1]
        else:typed.append(c)
    msvcrt.putwch('\r');msvcrt.putwch('\n')
    return ''.join(typed)

def change_owner_password(data_dir,username,password):
    from app import Shop
    from staff_access import StaffAccess
    access=StaffAccess(data_dir,'http://localhost',False,local=True,shop=Shop(data_dir))
    with access.shop.connect() as db:
        user=db.execute("SELECT id FROM web_users WHERE username=? AND role='owner' AND active=1",(str(username).lower(),)).fetchone()
    if not user:raise ValueError('Active owner account not found. No account changed.')
    access.password({'id':user['id'],'password':password})

def reset_owner(data_dir,username):
    """Prompt for a new owner password. Works only from the Windows account that owns the data."""
    _console();code=0
    try:
        password=_secret('New password (12 to 256 characters): ')
        if password!=_secret('Repeat new password: '):raise ValueError('Passwords differ. No account changed.')
        change_owner_password(data_dir,username,password)
        _say('Owner password changed; existing owner sessions signed out.')
    except (ValueError,KeyboardInterrupt) as error:
        _say(str(error) or 'Cancelled. No account changed.');code=1
    if os.name=='nt':_secret('Press Enter to close.')
    return code
