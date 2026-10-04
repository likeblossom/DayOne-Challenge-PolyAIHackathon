"""Create the judge-import ZIP without modifying checkpoints or exports."""
import hashlib,json,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'vision_pipeline/mobile_install_all_forms'
TARGET=ROOT/'dist/Sanad-models-v1.zip'

def main():
    TARGET.parent.mkdir(exist_ok=True)
    raw=(SOURCE/'manifest.json').read_bytes();manifest=json.loads(raw)
    expected='647b08a32d9e70af6e3d564f56d8c974345b1b0d321d37d9843fe7018c13d2bf'
    assert hashlib.sha256(raw).hexdigest()==expected,'Pack differs from APK pinned manifest'
    partial=TARGET.with_suffix('.zip.partial')
    try:
        with zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
            archive.writestr('manifest.json',raw)
            for name,info in sorted(manifest['files'].items()):
                path=SOURCE/name;assert path.is_relative_to(SOURCE) and '..' not in Path(name).parts
                digest=hashlib.sha256();size=0
                with path.open('rb') as src,archive.open(name,'w',force_zip64=True) as dest:
                    while chunk:=src.read(1024*1024):digest.update(chunk);dest.write(chunk);size+=len(chunk)
                assert size==info['bytes'] and digest.hexdigest()==info['sha256'],name
        partial.replace(TARGET)
    except BaseException:
        partial.unlink(missing_ok=True);raise
    digest=hashlib.sha256()
    with TARGET.open('rb') as stream:
        while chunk:=stream.read(1024*1024):digest.update(chunk)
    TARGET.with_suffix('.zip.sha256').write_text(digest.hexdigest()+'  '+TARGET.name+'\n')
    print(TARGET);print(TARGET.stat().st_size,'bytes')
if __name__=='__main__':main()
