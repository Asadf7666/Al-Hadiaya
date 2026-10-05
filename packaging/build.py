"""Build a Windows NSIS installer on Linux or Windows; no shop-side Python needed."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='3.14.8'
SHA256='a93abe456ab01bd96d7a085b3cdb6566b3063f4241360d114142fbdb07f0a310'
def main():
    compiler=os.environ.get('MAKENSIS') or shutil.which('makensis')
    if not compiler and os.name=='nt':
        compiler=str(Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'NSIS'/'makensis.exe')
    if not compiler or not Path(compiler).is_file():
        raise SystemExit('Install NSIS 3 and set MAKENSIS to its compiler executable if it is not on PATH.')
    build=ROOT/'build';build.mkdir(exist_ok=True)
    archive=build/'python-embed.zip'
    if not archive.exists():
        with urllib.request.urlopen(f'https://www.python.org/ftp/python/{VERSION}/python-{VERSION}-embed-amd64.zip',timeout=60) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:
        raise SystemExit('Embedded runtime SHA-256 mismatch. Packaging aborted.')
    runtime=build/'runtime'
    runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:z.extractall(runtime)
    (ROOT/'dist').mkdir(exist_ok=True)
    subprocess.run([compiler,'launcher.nsi'],cwd=ROOT/'packaging',check=True)
    subprocess.run([compiler,'installer.nsi'],cwd=ROOT/'packaging',check=True)
    setup=ROOT/'dist'/'AlHidayaTraders-Setup-0.2.0.exe'
    digest=hashlib.sha256(setup.read_bytes()).hexdigest()
    (setup.parent/'SHA256SUMS.txt').write_text(digest+'  '+setup.name+'\n')
    print('Built:',setup,'\nSHA-256:',digest)
if __name__=='__main__':main()
