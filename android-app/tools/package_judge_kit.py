"""Bundle the signed APK, importable model ZIP and plain-text instructions."""
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / 'dist'
TARGET = DIST / 'Sanad-v0.2.0-judge-kit.zip'


def main():
    files = {
        'README.txt': ROOT / 'android-app/JUDGE_README.txt',
        'Sanad-v0.2.0.apk': DIST / 'Sanad-v0.2.0.apk',
        'Sanad-models-v1.zip': DIST / 'Sanad-models-v1.zip',
    }
    for path in files.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    required = sum(path.stat().st_size for path in files.values())
    if shutil.disk_usage(DIST).free < required + 256 * 1024**2:
        raise RuntimeError('Not enough space to create the judge kit safely')
    partial = TARGET.with_suffix('.zip.partial')
    try:
        with zipfile.ZipFile(partial, 'w', compression=zipfile.ZIP_STORED,
                             allowZip64=True) as archive:
            for name, path in files.items():
                archive.write(path, name)
        with zipfile.ZipFile(partial) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise RuntimeError(f'ZIP verification failed: {bad}')
        partial.replace(TARGET)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    print(f'{TARGET}\n{TARGET.stat().st_size} bytes; archive verified')


if __name__ == '__main__':
    main()
