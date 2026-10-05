"""Explicit debug-phone deployment through the real, atomic ZIP importer."""
import argparse
import fcntl
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

PACKAGE='org.dayone.midwife'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--serial',required=True)
    ap.add_argument('--zip',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    lock=open(Path(tempfile.gettempdir())/('sanad-benchmark-'+hashlib.sha256(args.serial.encode()).hexdigest()[:16]+'.lock'),'a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.output.exists():raise FileExistsError('Choose a new deployment report directory')
    with zipfile.ZipFile(args.zip) as archive:
        first=archive.infolist()[0]
        if first.filename!='manifest.json' or first.file_size>1024*1024:raise ValueError('Not a Sanad model ZIP')
        manifest=archive.read(first)
    digest=hashlib.sha256()
    with args.zip.open('rb') as stream:
        while block:=stream.read(1024*1024):digest.update(block)
    request=dict(operation='install-live-model-pack',run_id=str(uuid.uuid4()),manifest_sha256=hashlib.sha256(manifest).hexdigest())
    args.output.mkdir(parents=True)
    adb=['adb','-s',args.serial]
    def run(*command,**kwargs):return subprocess.run(adb+list(command),capture_output=True,check=True,**kwargs).stdout
    paths=run('shell','pm','path',PACKAGE).decode().splitlines()
    base=next(p.removeprefix('package:') for p in paths if p.endswith('/base.apk'))
    apk_hash=run('shell','sha256sum',base).decode().split()[0]
    print('Staging model ZIP; saved records are not modified',flush=True)
    process=subprocess.Popen(adb+['exec-in','run-as',PACKAGE,'tar','xf','-','-C','files'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdin,mode='w|',dereference=True) as archive:
            archive.add(args.zip,arcname='benchmark/model-pack.zip',recursive=False)
            raw=json.dumps(request).encode();info=tarfile.TarInfo('benchmark/install-request.json');info.size=len(raw)
            archive.addfile(info,io.BytesIO(raw))
        process.stdin.close();process.stdin=None
        stdout,stderr=process.communicate(timeout=600)
        if process.returncode:raise RuntimeError(stderr.decode())
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=15)
    # exec-in may finish locally before the remote tar has flushed its final
    # entries. The trailing request is our completion marker, not pipe exit.
    deadline=time.monotonic()+180
    while True:
        try:
            staged=json.loads(run('exec-out','run-as',PACKAGE,'cat','files/benchmark/install-request.json'))
            size=int(run('shell','run-as',PACKAGE,'stat','-c','%s','files/benchmark/model-pack.zip').decode().strip())
            if staged==request and size==args.zip.stat().st_size:break
        except (subprocess.CalledProcessError,ValueError):pass
        if time.monotonic()>deadline:raise TimeoutError('Remote ZIP staging did not finish; live models were not changed')
        time.sleep(1)
    print('Verifying and importing through ModelPackInstaller',flush=True)
    with (args.output/'instrumentation.txt').open('x') as log:
        subprocess.run(adb+['shell','am','instrument','-w','-e','class',PACKAGE+'.ModelPackImportTest#testExplicitLivePackImportPreservesVault',
                           PACKAGE+'.test/android.test.InstrumentationTestRunner'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
    result=json.loads(run('exec-out','run-as',PACKAGE,'cat','files/benchmark/install-result.json'))
    if result.get('run_id')!=request['run_id'] or result.get('status')!='ok':raise ValueError('Missing matching import confirmation; inspect instrumentation log')
    result.update(apk_sha256=apk_hash,zip_sha256=digest.hexdigest(),zip_path=str(args.zip.resolve()))
    (args.output/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
