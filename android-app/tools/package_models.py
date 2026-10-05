"""Create the judge-import ZIP without modifying checkpoints or exports."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'vision_pipeline/mobile_install_all_forms'
TARGET=ROOT/'dist/Sanad-models-v1.zip'

def package(source,target,expected):
    source=source.resolve();target=target.resolve();partial=target.with_suffix('.zip.partial')
    checksum=target.with_suffix('.zip.sha256')
    if target.exists() or partial.exists() or checksum.exists():raise FileExistsError('Choose a new output; existing packs are never overwritten')
    raw=(source/'manifest.json').read_bytes();manifest=json.loads(raw)
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Pack differs from APK pinned manifest; choose the matching --source')
    target.parent.mkdir(parents=True,exist_ok=True)
    stream=partial.open('xb')
    try:
        with stream,zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
            archive.writestr('manifest.json',raw)
            for name,info in sorted(manifest['files'].items()):
                if Path(name).is_absolute() or '\\' in name or any(part in ('','.','..') for part in name.split('/')):raise ValueError('Unsafe model path: '+name)
                path=source/name
                digest=hashlib.sha256();size=0
                with path.open('rb') as src,archive.open(name,'w',force_zip64=True) as dest:
                    while chunk:=src.read(1024*1024):digest.update(chunk);dest.write(chunk);size+=len(chunk)
                if size!=info['bytes'] or digest.hexdigest()!=info['sha256']:raise ValueError('Damaged model: '+name)
        if target.exists():raise FileExistsError('Output appeared during packaging; refusing replacement')
        partial.replace(target)
    except BaseException:
        partial.unlink(missing_ok=True);raise
    digest=hashlib.sha256()
    with target.open('rb') as stream:
        while chunk:=stream.read(1024*1024):digest.update(chunk)
    with checksum.open('x') as stream:stream.write(digest.hexdigest()+'  '+target.name+'\n')
    return dict(path=str(target),bytes=target.stat().st_size,sha256=digest.hexdigest())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=SOURCE);parser.add_argument('--output',type=Path,default=TARGET)
    args=parser.parse_args()
    code=(ROOT/'android-app/app/src/main/java/org/dayone/midwife/ModelPackInstaller.java').read_text()
    match=re.search(r'MANIFEST_SHA256\s*=\s*"([0-9a-f]{64})"',code)
    if not match:raise ValueError('Cannot find the APK manifest pin')
    print(json.dumps(package(args.source,args.output,match.group(1)),indent=2))
if __name__=='__main__':main()
