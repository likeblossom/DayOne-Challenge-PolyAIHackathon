"""Install locally generated models without sending anything to a server.

Run with the target device explicitly selected when several devices are attached.
This never replaces the original training checkpoints or user records.
"""
import argparse,subprocess,tarfile
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[2]
    p=argparse.ArgumentParser();p.add_argument('--serial');p.add_argument('--fixtures',action='store_true');p.add_argument('--bundle',type=Path,default=root/'vision_pipeline/mobile_install_all_forms');a=p.parse_args()
    if not (a.bundle/'manifest.json').is_file():raise SystemExit('Build the eight-form model pack first: python -m vision_pipeline.all_forms.mobile')
    adb=['adb']+(['-s',a.serial] if a.serial else [])
    target='files/sanad-models-v1';package='org.dayone.midwife'
    subprocess.run(adb+['shell','run-as',package,'mkdir','-p',target],check=True)
    # Stream bounded chunks directly into DEBUG app-private storage as the app UID.
    # No root, shared-storage permissions, temporary copy or multi-GB APK required.
    proc=subprocess.Popen(adb+['exec-in','run-as',package,'tar','xf','-','-C','files'],stdin=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdin,mode='w|') as archive:
            for path in sorted(p for p in a.bundle.rglob('*') if p.is_file() and p.name!='manifest.json'):
                archive.add(path,arcname='sanad-models-v1/'+str(path.relative_to(a.bundle)),recursive=False)
            archive.add(a.bundle/'manifest.json',arcname='sanad-models-v1/manifest.json',recursive=False)
            if a.fixtures:
                archive.add(root/'vision_pipeline/outputs/unit_grammar/page_06/relative/ocr/weight_g/numeric/crop_before_processor.png',arcname='mobile-test-numeric.png',recursive=False)
                for number in range(1,9):
                    archive.add(root/f'data/organizer/data/Paper Registry/dossiers_specimen_10_patientes-{number:02d}.png',arcname=f'mobile-test-form{number:02d}.png',recursive=False)
        proc.stdin.close()
        if proc.wait()!=0:raise RuntimeError('Model transfer failed; incomplete pack will be rejected.')
    except BaseException:
        proc.kill();proc.wait();raise
    print('Installed model pack in app-private',target,flush=True)
if __name__=='__main__':main()
