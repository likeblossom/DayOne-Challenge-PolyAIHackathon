"""Sequential, real-phone organizer benchmark; never edits user records or models."""
import argparse
import collections
import fcntl
import hashlib
import io
import json
import re
import subprocess
import tarfile
import time
import tempfile
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'org.dayone.midwife'


def write_json_atomic(path,value):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    temporary.replace(path)


def normalized(value):
    if isinstance(value, str):
        return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if c.isalnum())
    return value


def lookup(fields, path):
    current = fields
    try:
        for part in re.findall(r'[^.\[\]]+', path):
            current = current[int(part)] if isinstance(current, list) else current[part]
        if isinstance(current, list):
            return [item.get('value') for item in current], None
        return current.get('value'), current.get('status')
    except (KeyError, IndexError, TypeError, AttributeError):
        return None, None


def equal(a, b):
    if isinstance(b, list):
        return isinstance(a, list) and sorted(map(str, a)) == sorted(map(str, b))
    return type(a) is type(b) and a == b if isinstance(b, bool) else a == b


def score(result, truth):
    counts = collections.Counter()
    rows = []
    form_ok = result.get('form_id') == truth['form_id'].split('_', 1)[1]
    for key, field in truth['fields'].items():
        if not field.get('score_eligible') or field['kind'] == 'printed':
            continue
        value, status = lookup(result.get('fields', {}), key)
        exact = form_ok and equal(value, field['value'])
        norm = form_ok and equal(normalized(value), normalized(field['value']))
        counts['fields'] += 1
        counts['exact'] += int(exact)
        counts['normalized'] += int(norm)
        counts['status_correct'] += int(form_ok and status == field['status'])
        if status=='KNOWN':
            counts['known_predictions']+=1
            counts['known_predictions_correct']+=int(norm)
            counts['known_predictions_wrong']+=int(not norm)
        if field['kind'] == 'text' and field['status'] == 'KNOWN':
            counts['filled_text'] += 1
            counts['filled_text_exact'] += int(exact)
            counts['filled_text_normalized'] += int(norm)
            counts['filled_text_reported_blank'] += int(status=='NOT_PROVIDED')
        rows.append(dict(field=key, expected=field['value'], actual=value,
                         expected_status=field['status'], actual_status=status,
                         exact=exact, normalized=norm))
    return dict(form_correct=form_ok, counts=dict(counts), fields=rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--serial', required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--per-form', type=int, default=1)
    ap.add_argument('--forms', default='1,2,3,4,5,6,7,8')
    ap.add_argument('--cases',help='Optional comma-separated case IDs; selection must include every requested ID')
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--classifier-only', action='store_true')
    ap.add_argument('--capture-crops', action='store_true')
    ap.add_argument('--interleave', action='store_true', help='Test one page of every form before the next round')
    ap.add_argument('--resume',action='store_true',help='Skip completed cases only when APK, model, references and mode match')
    ap.add_argument('--labels',type=Path,default=ROOT/'data/processed/organizer_test/labels.jsonl')
    ap.add_argument('--model-directory',default='sanad-models-v1')
    ap.add_argument('--scope',default='Android CPU; provisional organizer PDF-vector references; development benchmark')
    args = ap.parse_args()
    if args.classifier_only and args.capture_crops:ap.error('Classifier-only mode has no field crops')
    # One phone and one request directory: concurrent runs would invalidate evidence.
    lock = open(Path(tempfile.gettempdir()) / ('sanad-benchmark-' + hashlib.sha256(args.serial.encode()).hexdigest()[:16] + '.lock'), 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    args.output.mkdir(parents=True, exist_ok=True)
    previous_path=args.output/'summary.json'
    if previous_path.exists() and not args.resume:
        ap.error('Output already contains results; use a fresh output or --resume')
    adb = ['adb', '-s', args.serial]

    def run(*command, **kw):
        return subprocess.run(adb + list(command), check=True, capture_output=True, **kw).stdout

    if args.per_form<1 or args.timeout<1:ap.error('Sample count and timeout must be positive')
    rows = [json.loads(s) for s in args.labels.read_text().splitlines()]
    wanted = set(map(int, args.forms.split(',')))
    wanted_cases=set(args.cases.split(',')) if args.cases else None
    selected = []
    seen = collections.Counter()
    for row in sorted(rows, key=lambda r: (r['form_id'], r['pdf_page'])):
        if wanted_cases is not None and row.get('case_id',f"page_{row['pdf_page']:02d}") not in wanted_cases:continue
        form = int(row['form_id'].split('_', 1)[0])
        if form in wanted and seen[form] < args.per_form:
            selected.append(row)
            seen[form] += 1
    if wanted_cases is not None and {row.get('case_id',f"page_{row['pdf_page']:02d}") for row in selected}!=wanted_cases:
        ap.error('Requested cases were excluded; check IDs, --forms and --per-form')
    if args.interleave:
        rounds=collections.Counter();ranked=[]
        for row in selected:
            ranked.append((rounds[row['form_id']],row['form_id'],row));rounds[row['form_id']]+=1
        selected=[row for _,_,row in sorted(ranked,key=lambda item:item[:2])]
    summary = dict(scope=args.scope,
                   serial=args.serial, cases=[], counts={}, failures=0)
    apk_paths=run('shell','pm','path',PACKAGE).decode().splitlines()
    base=next(path.removeprefix('package:') for path in apk_paths if path.endswith('/base.apk'))
    summary['apk_sha256']=run('shell','sha256sum',base).decode().split()[0]
    if args.model_directory!='sanad-models-v1' and not re.fullmatch('benchmark-models-[A-Za-z0-9_-]+',args.model_directory):ap.error('Invalid model directory')
    summary['model_directory']=args.model_directory
    summary['model_manifest_sha256']=hashlib.sha256(run('exec-out','run-as',PACKAGE,'cat',f'files/{args.model_directory}/manifest.json')).hexdigest()
    summary['labels_sha256']=hashlib.sha256(args.labels.read_bytes()).hexdigest()
    summary['labels_path']=str(args.labels.resolve())
    summary['normalization']='NFKD casefold alphanumeric only; not clinical equivalence; blank fields included in all-field score'
    summary['classifier_only']=args.classifier_only
    summary['capture_crops']=args.capture_crops
    requested={r.get('case_id',f"page_{r['pdf_page']:02d}") for r in selected}
    summary['requested_cases']=sorted(requested)
    total = collections.Counter()
    completed=set()
    if args.resume and previous_path.exists():
        previous=json.loads(previous_path.read_text())
        for key in ['serial','apk_sha256','model_manifest_sha256','labels_sha256','classifier_only','capture_crops']:
            if previous.get(key)!=summary[key]:raise ValueError('Cannot resume with changed or unverified '+key)
        for case in previous['cases']:
            folder=args.output/case['case_id']
            if not (folder/'result.json').is_file() or not (folder/'score.json').is_file():
                raise ValueError('Missing immutable case evidence: '+case['case_id'])
            completed.add(case['case_id']);total.update(case['counts'])
        summary['cases']=previous['cases'];summary['failures']=previous['failures'];summary['counts']=dict(total)
        if not completed<=requested:raise ValueError('Resume selection would exclude previously completed cases')
    for truth in selected:
        # Avoid sustained thermal stress during multi-hour device evaluations.
        while True:
            battery=run('shell','dumpsys','battery').decode()
            temperature=re.search(r'\btemperature:\s*(\d+)',battery)
            if not temperature or int(temperature.group(1))<440:break
            print('COOLING: waiting for battery temperature below 44 C',flush=True)
            time.sleep(30)
        case_id = truth.get('case_id',f"page_{truth['pdf_page']:02d}")
        if not re.fullmatch('[A-Za-z0-9_-]+',case_id):raise ValueError('Unsafe benchmark case id')
        if case_id in completed:continue
        folder = args.output / case_id
        folder.mkdir(exist_ok=True)
        image = ROOT / truth['image']
        run_id = str(uuid.uuid4())
        image_hash=hashlib.sha256(image.read_bytes()).hexdigest()
        if truth.get('image_sha256') and truth['image_sha256']!=image_hash:
            raise ValueError('Reference image checksum mismatch: '+case_id)
        request = json.dumps(dict(case_id=case_id, run_id=run_id, sha256=image_hash,
                                  capture_crops=args.capture_crops,model_directory=args.model_directory)).encode()
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode='w') as archive:
            archive.add(image, arcname='benchmark/input.png', recursive=False)
            info = tarfile.TarInfo('benchmark/request.json')
            info.size = len(request)
            archive.addfile(info, io.BytesIO(request))
        run('exec-in', 'run-as', PACKAGE, 'tar', 'xf', '-', '-C', 'files', input=payload.getvalue())
        print(f'START {case_id} {truth["form_id"]}', flush=True)
        started = time.monotonic()
        pss = []
        timed_out=False
        with (folder / 'instrumentation.txt').open('w') as log:
            proc = subprocess.Popen(adb + ['shell', 'am', 'instrument', '-w', '-e', 'class',
                PACKAGE + '.BenchmarkTest#' + ('testClassifier' if args.classifier_only else 'testCase'), PACKAGE + '.test/android.test.InstrumentationTestRunner'],
                stdout=log, stderr=subprocess.STDOUT)
            while proc.poll() is None:
                if time.monotonic() - started > args.timeout:
                    timed_out=True
                    run('shell', 'am', 'force-stop', PACKAGE)
                    proc.terminate()
                    proc.wait(timeout=15)
                    break
                try:
                    memory = run('shell', 'dumpsys', 'meminfo', PACKAGE, timeout=10).decode()
                    match = re.search(r'TOTAL PSS:\s*(\d+)', memory)
                    if match:
                        pss.append(int(match.group(1)))
                except (subprocess.SubprocessError, OSError):
                    pass
                time.sleep(1 if args.classifier_only else 5)
        try:
            if timed_out:raise ValueError('Instrumentation timed out')
            result = json.loads(run('exec-out', 'run-as', PACKAGE, 'cat', 'files/benchmark/result.json'))
            if result.get('case_id') != case_id or result.get('run_id') != run_id:
                raise ValueError('Stale output from previous case')
        except (subprocess.SubprocessError, ValueError):
            result = dict(case_id=case_id, status='crash_or_timeout', error='No matching result; see instrumentation log')
        result['wall_seconds'] = round(time.monotonic() - started, 2)
        if args.classifier_only and result.get('status') == 'ok':
            (folder / 'classifier.png').write_bytes(run('exec-out', 'run-as', PACKAGE, 'cat', 'files/benchmark/classifier.png'))
        if args.capture_crops and result.get('status') == 'ok':
            (folder / 'crops.tar').write_bytes(run('exec-out', 'run-as', PACKAGE, 'tar', 'cf', '-', '-C',
                                                 'files/benchmark/crops/' + case_id + '/' + run_id, '.'))
        result['sampled_peak_pss_kb'] = max(pss, default=None)
        write_json_atomic(folder/'result.json',result)
        if args.classifier_only:
            correct = result.get('status') == 'ok' and result.get('label') == str(int(truth['form_id'].split('_')[0])-1)
            accepted=result.get('status')=='ok' and result.get('confidence',0)>=.75
            scored = dict(form_correct=correct, counts=dict(pages=1, correct=int(correct),
                accepted_correct=int(accepted and correct),confident_wrong=int(accepted and not correct),abstained=int(not accepted)))
        else:
            scored = score(result, truth)
        write_json_atomic(folder/'score.json',scored)
        total.update(scored['counts'])
        summary['failures'] += result.get('status') != 'ok'
        summary['cases'].append(dict(case_id=case_id, form=truth['form_id'], status=result['status'],
            wall_seconds=result['wall_seconds'], sampled_peak_pss_kb=result['sampled_peak_pss_kb'],
            form_correct=scored['form_correct'], counts=scored['counts']))
        summary['counts'] = dict(total)
        write_json_atomic(args.output/'summary.json',summary)
        print(f"DONE {case_id} {result['status']} {result['wall_seconds']}s {scored['counts']}", flush=True)
    print(args.output / 'summary.json', flush=True)


if __name__ == '__main__':
    main()
