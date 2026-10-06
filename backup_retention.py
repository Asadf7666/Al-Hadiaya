"""Bound periodic snapshot disk use; preserve manual/update/recovery snapshots."""
import re,shutil
from pathlib import Path
def prune(folder):
 files=sorted((p for p in Path(folder).glob('AlHidaya-Auto-*.sqlite3') if re.fullmatch(r'AlHidaya-Auto-[0-9]{8}-[0-9]{6}-[0-9]{6}\.sqlite3',p.name)),reverse=True)
 keep=set(files[:8]);days={}
 for p in files:days.setdefault(p.name.split('-')[2],p)
 keep.update(list(days.values())[:7])
 for p in files:
  if p not in keep:
   p.unlink();media=p.with_suffix('.media')
   if media.exists():shutil.rmtree(media)
