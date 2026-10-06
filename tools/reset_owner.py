"""Recover a local owner password from the Windows account that owns the data."""
import argparse,getpass,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Shop,DATA
from staff_access import StaffAccess
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--data-dir',default=str(DATA));parser.add_argument('--username',required=True);args=parser.parse_args()
 access=StaffAccess(args.data_dir,'http://localhost',False,local=True,shop=Shop(args.data_dir))
 with access.shop.connect() as db:user=db.execute("SELECT id FROM web_users WHERE username=? AND role='owner' AND active=1",(args.username.lower(),)).fetchone()
 if not user:raise SystemExit('Active owner account not found. No account changed.')
 password=getpass.getpass('New password (12–256 characters): ')
 if password!=getpass.getpass('Repeat new password: '):raise SystemExit('Passwords differ. No account changed.')
 access.password({'id':user['id'],'password':password});print('Owner password changed; existing owner sessions signed out.')
if __name__=='__main__':main()
