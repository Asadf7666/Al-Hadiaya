"""Recover a local owner password when running from source. The installed program uses --reset-owner."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import DATA
import maintenance
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--data-dir',default=str(DATA));parser.add_argument('--username',required=True);args=parser.parse_args()
 raise SystemExit(maintenance.reset_owner(args.data_dir,args.username))
if __name__=='__main__':main()
