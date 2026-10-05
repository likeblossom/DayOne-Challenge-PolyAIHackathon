"""Stage a private benchmark pack, copying unchanged weights locally on the phone."""
import argparse
import hashlib
import json
import re
import shlex
import subprocess
import tarfile
from pathlib import Path,PurePosixPath


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--serial',required=True);ap.add_argument('--pack',type=Path,required=True);ap.add_argument('--name',required=True)
    ap.add_argument('--base-directory',default='sanad-models-v1',help='Existing phone pack used only as a copy source');args=ap.parse_args()
    if not re.fullmatch('benchmark-models-[A-Za-z0-9_-]+',args.name):ap.error('Use a benchmark-models-... directory')
    if args.base_directory!='sanad-models-v1' and not re.fullmatch('benchmark-models-[A-Za-z0-9_-]+',args.base_directory):ap.error('Invalid source directory')
    adb=['adb','-s',args.serial];package='org.dayone.midwife'
    def run(*command,**kw):return subprocess.run(adb+list(command),check=True,capture_output=True,**kw).stdout
    exists=subprocess.run(adb+['shell','run-as',package,'test','-e','files/'+args.name]).returncode==0
    if exists:raise FileExistsError('Choose a new candidate directory; never overwrite model files')
    base=json.loads(run('exec-out','run-as',package,'cat','files/'+args.base_directory+'/manifest.json'))
    raw=(args.pack/'manifest.json').read_bytes();manifest=json.loads(raw);commands=[];changed=[]
    for name,info in manifest['files'].items():
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe manifest path')
        file=args.pack/name
        if file.stat().st_size!=info['bytes']:raise ValueError('Size mismatch: '+name)
        if base['files'].get(name)==info:
            target='files/'+args.name+'/'+name
            commands.append('mkdir -p '+shlex.quote(str(PurePosixPath(target).parent)))
            commands.append('cp '+shlex.quote('files/'+args.base_directory+'/'+name)+' '+shlex.quote(target))
        else:
            digest=hashlib.sha256()
            with file.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
            if digest.hexdigest()!=info['sha256']:raise ValueError('Hash mismatch: '+name)
            changed.append(name)
    run('shell','run-as',package,'sh','-c',shlex.quote('set -eu\n'+'\n'.join(commands)+'\n'))
    process=subprocess.Popen(adb+['exec-in','run-as',package,'tar','xf','-','-C','files'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdin,mode='w|',dereference=True) as archive:
            for name in changed+['manifest.json']:archive.add(args.pack/name,arcname=args.name+'/'+name,recursive=False)
        process.stdin.close();process.stdin=None
        stdout,stderr=process.communicate(timeout=600)
        if process.returncode:raise RuntimeError(stderr.decode())
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=15)
    for name in manifest['files']:
        run('shell','run-as',package,'test','-f','files/'+args.name+'/'+name)
    print(json.dumps(dict(directory=args.name,changed_files=changed,locally_copied_files=len(manifest['files'])-len(changed),live_pack_unchanged=True)),flush=True)


if __name__=='__main__':main()
