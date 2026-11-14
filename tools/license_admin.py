"""Vendor tool: create the signing key and issue licence files. Never ship this or the key.

  python tools/license_admin.py keygen  --key signing.key
  python tools/license_admin.py issue   --key signing.key --customer "Shop name" --machine 1A2B-3C4D-5E6F-7A8B --days 365 --out shop.lic
  python tools/license_admin.py inspect shop.lic
"""
import argparse,datetime as dt,os,secrets,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import licensing

def load_key(path):
    try:seed=bytes.fromhex(Path(path).read_text().strip())
    except (OSError,ValueError):raise SystemExit('Signing key not found or unreadable: '+str(path))
    if len(seed)!=32:raise SystemExit('The signing key file is damaged.')
    return seed

def keygen(args):
    path=Path(args.key)
    if path.exists():raise SystemExit('A key already exists there. Replacing it would invalidate every licence issued with it.')
    seed=secrets.token_bytes(32)
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as handle:handle.write(seed.hex()+'\n')
    print('Signing key written to',path,'\nKeep it private and backed up offline.\nPublic key for licensing.py PUBLIC_KEY:',licensing.public_key(seed).hex())

def issue(args):
    seed=load_key(args.key)
    if licensing.public_key(seed).hex()!=licensing.PUBLIC_KEY:
        raise SystemExit('This key does not match the public key built into the app, so its licences would be rejected.')
    today=dt.date.today()
    if args.perpetual:expires=None
    elif args.expires:expires=dt.date.fromisoformat(args.expires).isoformat()
    elif args.days:expires=(today+dt.timedelta(days=args.days)).isoformat()
    else:raise SystemExit('Choose --days, --expires or --perpetual.')
    if expires and expires<today.isoformat():raise SystemExit('That expiry date has already passed.')
    payload={'v':1,'product':licensing.PRODUCT,'id':args.id or 'AHT-'+today.strftime('%Y%m%d')+'-'+secrets.token_hex(3).upper(),
             'customer':args.customer.strip(),'edition':args.edition,'issued':today.isoformat(),'expires':expires,
             'machine':'*' if args.any_machine else licensing.normalise_machine(args.machine)}
    if not payload['customer']:raise SystemExit('Enter the customer name.')
    text=licensing.pack(payload,seed);licensing.parse(text)
    out=Path(args.out or payload['id']+'.lic');out.write_text(text,encoding='utf-8')
    print('Licence',payload['id'],'for',payload['customer'],'\nPC:',payload['machine'],'\nExpires:',expires or 'never','\nFile:',out)

def inspect(args):
    try:payload=licensing.parse(Path(args.file).read_text(encoding='utf-8'))
    except (OSError,ValueError) as error:raise SystemExit('Not valid: '+str(error))
    for key in ('id','customer','edition','machine','issued','expires'):print(f'{key:9}',payload.get(key) if payload.get(key) is not None else 'never')

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    commands=parser.add_subparsers(dest='command',required=True)
    k=commands.add_parser('keygen');k.add_argument('--key',required=True);k.set_defaults(run=keygen)
    i=commands.add_parser('issue');i.add_argument('--key',required=True);i.add_argument('--customer',required=True)
    target=i.add_mutually_exclusive_group(required=True)
    target.add_argument('--machine',help='Installation ID shown on the Licence page of the PC');target.add_argument('--any-machine',action='store_true',help='Not tied to one PC')
    i.add_argument('--days',type=int);i.add_argument('--expires',help='YYYY-MM-DD');i.add_argument('--perpetual',action='store_true')
    i.add_argument('--edition',default='Standard');i.add_argument('--id');i.add_argument('--out');i.set_defaults(run=issue)
    v=commands.add_parser('inspect');v.add_argument('file');v.set_defaults(run=inspect)
    args=parser.parse_args()
    try:args.run(args)
    except ValueError as error:raise SystemExit(str(error))

if __name__=='__main__':main()
