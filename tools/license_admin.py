"""Vendor tool: create the signing key and issue licence files. Never ship this or the key.

  python tools/license_admin.py keygen  --key signing.key
  python tools/license_admin.py issue   --key signing.key --customer "Shop name" --type first --days 365 --out shop.lic
  python tools/license_admin.py issue   --key signing.key --customer "Shop name" --type single --machine 1A2B-3C4D-5E6F-7A8B --perpetual --support-until 2027-11-15
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
    today=dt.date.today();kind=args.type or ('single' if args.machine else 'site')
    if kind=='single' and not args.machine:raise SystemExit('A single-PC licence needs --machine with the Installation ID from the Licence screen.')
    if kind!='single' and args.machine:raise SystemExit('Only a single-PC licence takes --machine.')
    if args.perpetual:expires=None
    elif args.expires:expires=dt.date.fromisoformat(args.expires).isoformat()
    elif args.days:expires=(today+dt.timedelta(days=args.days)).isoformat()
    else:raise SystemExit('Choose --days, --expires or --perpetual.')
    if expires and expires<today.isoformat():raise SystemExit('That expiry date has already passed.')
    if kind=='trial' and not expires:raise SystemExit('An evaluation licence needs --days or --expires.')
    payload={'v':2,'product':licensing.PRODUCT,'type':kind,'id':args.id or 'AHT-'+today.strftime('%Y%m%d')+'-'+secrets.token_hex(3).upper(),
             'customer':args.customer.strip(),'edition':args.edition,'issued':today.isoformat(),'expires':expires,
             'machine':licensing.normalise_machine(args.machine) if kind=='single' else '*'}
    if kind=='first':payload['activate_by']=(today+dt.timedelta(days=args.activate_within)).isoformat()
    if args.support_until:payload['support_until']=dt.date.fromisoformat(args.support_until).isoformat()
    if args.features is not None:
        payload['features']=[f for f in args.features.split(',') if f]
        unknown=[f for f in payload['features'] if f not in licensing.FEATURES]
        if unknown:raise SystemExit('Unknown feature: '+', '.join(unknown)+'. Choose from '+', '.join(licensing.FEATURES)+'.')
    if not payload['customer']:raise SystemExit('Enter the customer name.')
    text=licensing.pack(payload,seed);licensing.parse(text)
    out=Path(args.out or payload['id']+'.lic');out.write_text(text,encoding='utf-8')
    print('Licence',payload['id'],'for',payload['customer'],'\nType:',licensing.TYPES[kind],'\nPC:',payload['machine'] if kind=='single' else 'first PC it is installed on, by '+payload['activate_by'] if kind=='first' else 'any',
          '\nExpires:',expires or 'never','\nSupport until:',payload.get('support_until','not limited'),'\nFeatures:',', '.join(payload['features']) if 'features' in payload else 'all','\nFile:',out)

def inspect(args):
    try:payload=licensing.parse(Path(args.file).read_text(encoding='utf-8'))
    except (OSError,ValueError) as error:raise SystemExit('Not valid: '+str(error))
    for key in ('id','customer','type','edition','machine','issued','expires','activate_by','support_until','features'):
        if key in payload:print(f'{key:14}',payload[key] if payload[key] is not None else 'never')

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    commands=parser.add_subparsers(dest='command',required=True)
    k=commands.add_parser('keygen');k.add_argument('--key',required=True);k.set_defaults(run=keygen)
    i=commands.add_parser('issue');i.add_argument('--key',required=True);i.add_argument('--customer',required=True)
    i.add_argument('--type',choices=sorted(licensing.TYPES),help='single: one named PC. first: locks to the first PC it is installed on. site: any PC of the business. trial: dated evaluation.')
    i.add_argument('--machine',help='Installation ID from the Licence screen, for a single-PC licence')
    i.add_argument('--activate-within',type=int,default=licensing.ACTIVATION_DAYS,help='Days a first-PC licence may wait before its first installation')
    i.add_argument('--support-until',help='YYYY-MM-DD: the licence covers versions released up to this date')
    i.add_argument('--features',help='Comma-separated optional modules to include ('+', '.join(licensing.FEATURES)+'). Omit for all; pass an empty value for none.')
    i.add_argument('--days',type=int);i.add_argument('--expires',help='YYYY-MM-DD');i.add_argument('--perpetual',action='store_true')
    i.add_argument('--edition',default='Standard');i.add_argument('--id');i.add_argument('--out');i.set_defaults(run=issue)
    v=commands.add_parser('inspect');v.add_argument('file');v.set_defaults(run=inspect)
    args=parser.parse_args()
    try:args.run(args)
    except ValueError as error:raise SystemExit(str(error))

if __name__=='__main__':main()
