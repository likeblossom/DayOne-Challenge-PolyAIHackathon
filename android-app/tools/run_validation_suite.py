"""Sequential phone regression sets. Keeps organizer, stress, and synthetic scores separate."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SETS={
    'organizer':('data/processed/organizer_test_v4/labels.jsonl',10,
                 'Android CPU; organizer PDF-derived references with two adjudicated fields; development evaluation'),
    'stress':('data/processed/android_audit/stress_cases_v3/labels.jsonl',4,
              'Android CPU; transformed organizer development images; rotation, zoom-out, blur/JPEG and high-resolution cases'),
    'multilingual':('data/processed/android_audit/synthetic_multilingual_cases.jsonl',3,
                    'Android CPU; held-out synthetic font examples in English, French and Arabic; not real handwriting accuracy'),
    'camera':('data/processed/android_audit/camera_cases_v1.jsonl',5,
              'Android CPU; alternate-layout organizer camera images; sparse provisional references; primarily rejection-path evaluation'),
}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--serial',required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--model-directory',default='sanad-models-v1')
    ap.add_argument('--sets',nargs='+',choices=list(SETS),default=list(SETS))
    ap.add_argument('--resume',action='store_true');args=ap.parse_args()
    if args.output.exists() and not args.resume:raise FileExistsError('Choose a new suite output or explicitly resume')
    args.output.mkdir(parents=True,exist_ok=True)
    results={}
    for name in args.sets:
        labels,count,scope=SETS[name];output=args.output/name
        command=[sys.executable,str(ROOT/'android-app/tools/benchmark_android.py'),
                 '--serial',args.serial,'--output',str(output),'--model-directory',args.model_directory,
                 '--labels',str(ROOT/labels),'--per-form',str(count),'--interleave','--capture-crops',
                 '--timeout','1800','--scope',scope]
        if args.resume:command.append('--resume')
        print('START SET',name,flush=True)
        with (args.output/(name+'.log')).open('a' if args.resume else 'x') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,cwd=ROOT)
        report=json.loads((output/'summary.json').read_text())
        results[name]={k:report[k] for k in ['scope','apk_sha256','model_manifest_sha256','counts','failures']}
        results[name]['completed_pages']=len(report['cases'])
        (args.output/'suite_summary.json').write_text(json.dumps(results,indent=2))
        print('DONE SET',name,json.dumps(results[name]),flush=True)


if __name__=='__main__':main()
