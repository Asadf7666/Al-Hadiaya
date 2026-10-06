"""Installer preflight: close the local app cleanly and back up data before updates."""
import json
import socket
import sys
import time
import urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app import Shop, DATA

def running():
    with socket.socket() as s:
        s.settimeout(.5)
        return s.connect_ex(('127.0.0.1',8765)) == 0

try:
    if running():
        # Ignore system proxies for strictly local installer communication.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        from notifications import protect
        control=DATA/'maintenance-credential.bin'
        if control.exists():token=protect(control.read_bytes(),decrypt=True).decode()
        else:
            with opener.open('http://127.0.0.1:8765/api/session',timeout=3) as r:token=json.load(r)['token']
        req = urllib.request.Request('http://127.0.0.1:8765/api/shutdown',data=b'{}',headers={'X-Shop-Token':token,'Content-Type':'application/json'})
        with opener.open(req,timeout=10) as r:
            json.load(r)
        for _ in range(40):
            if not running():break
            time.sleep(.25)
        if running():raise RuntimeError('App did not close. Close it and run the installer again.')
        time.sleep(1)
    if (DATA/'shop.sqlite3').exists():
        Shop().backup(local_only=True)
except Exception as e:
    if sys.stderr:
        print(str(e),file=sys.stderr)
    sys.exit(1)
