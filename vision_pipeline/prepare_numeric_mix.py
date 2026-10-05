"""Mix tight generated numeric fields with the original synthetic numeric curriculum."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
from .common import ROOT


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tight',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Keep existing datasets immutable')
    args.output.mkdir(parents=True);rows=[];sources=[]
    for source in [args.tight.resolve(),ROOT/'data/numbers']:
        labels=source/'labels.jsonl';sources.append(dict(path=str(labels),sha256=hashlib.sha256(labels.read_bytes()).hexdigest()))
        for row in map(json.loads,labels.read_text().splitlines()):
            row=dict(row,image=str((source/row['image']).resolve()));rows.append(row)
    (args.output/'labels.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    report=dict(sources=sources,counts=dict(collections.Counter(row['split'] for row in rows)),organizer_used=False,
        split_policy='Inherited disjoint font/page splits for field crops; original numbers also have disjoint value/unit groups. Combined corpus does not claim disjoint numeric values.')
    (args.output/'dataset.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':main()
