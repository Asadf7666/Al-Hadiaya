"""Compile the app to a native Windows program with Nuitka and wrap it in an NSIS installer.

The shop PC needs nothing else: no Python and no source files are installed.
Build machine: Python with `pip install nuitka`, a C compiler Nuitka can use, and NSIS 3.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def compile_native(target):
    """Translate every module to C and build one program folder with its data files."""
    version=(ROOT/'VERSION').read_text().strip()
    shutil.rmtree(target,ignore_errors=True)
    modules=sorted(p.stem for p in ROOT.glob('*.py') if p.stem!='app')
    command=[sys.executable,'-m','nuitka','--standalone','--assume-yes-for-downloads','--lto=no',
             '--output-dir='+str(target),'--output-filename=AlHidayaTraders',
             *('--include-module='+name for name in modules),
             '--include-data-dir=static=static','--include-data-files=VERSION=VERSION','--include-data-files=catalog.json=catalog.json',
             '--nofollow-import-to=tkinter,unittest,test,pydoc,doctest']
    if os.name=='nt':
        command+=['--windows-console-mode=disable','--company-name=Al Hadiya Traders','--product-name=Al Hadiya Traders',
                  '--file-description=Al Hadiya Traders business manager','--file-version='+version,'--product-version='+version]
    subprocess.run(command+['app.py'],cwd=ROOT,check=True)
    dist=target/'app.dist'
    leftovers=[p.name for p in dist.rglob('*') if p.suffix in ('.py','.pyc')]
    if leftovers:raise SystemExit('Python source or bytecode reached the program folder: '+', '.join(leftovers))
    return dist

def main():
    compiler=os.environ.get('MAKENSIS') or shutil.which('makensis')
    if not compiler and os.name=='nt':
        compiler=str(Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'NSIS'/'makensis.exe')
    if not compiler or not Path(compiler).is_file():
        raise SystemExit('Install NSIS 3 and set MAKENSIS to its compiler executable if it is not on PATH.')
    if os.name!='nt':
        raise SystemExit('Build the installer on Windows: Nuitka compiles for the system it runs on.')
    compile_native(ROOT/'build'/'native')
    (ROOT/'dist').mkdir(exist_ok=True)
    product_version=(ROOT/'VERSION').read_text().strip()
    subprocess.run([compiler,'/DPRODUCT_VERSION='+product_version,'installer.nsi'],cwd=ROOT/'packaging',check=True)
    setup=ROOT/'dist'/('AlHidayaTraders-Setup-'+product_version+'.exe')
    digest=hashlib.sha256(setup.read_bytes()).hexdigest()
    (setup.parent/'SHA256SUMS.txt').write_text(digest+'  '+setup.name+'\n')
    print('Built:',setup,'\nSHA-256:',digest)
if __name__=='__main__':main()
