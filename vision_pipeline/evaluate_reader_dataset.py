"""Evaluate a local reader on explicit synthetic split labels, without training."""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('USE_TF','0')
import torch
from PIL import Image
from transformers import TrOCRProcessor, NougatProcessor, VisionEncoderDecoderModel
from .date_ocr.train import edit_distance


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--checkpoint',type=Path,required=True)
    ap.add_argument('--dataset',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--split',default='val');ap.add_argument('--limit',type=int,default=100)
    args=ap.parse_args();torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.16)
    config=json.loads((args.checkpoint/'preprocessor_config.json').read_text())
    processor=(NougatProcessor if config['image_processor_type']=='NougatImageProcessor' else TrOCRProcessor).from_pretrained(args.checkpoint,local_files_only=True)
    model=VisionEncoderDecoderModel.from_pretrained(args.checkpoint,local_files_only=True).cuda().half().eval()
    labels=[json.loads(line) for line in (args.dataset/'labels.jsonl').read_text().splitlines() if json.loads(line)['split']==args.split]
    # Deterministic coverage throughout the split, not just the first form.
    if args.limit and len(labels)>args.limit:labels=[labels[i*len(labels)//args.limit] for i in range(args.limit)]
    rows=[]
    for label in labels:
        with Image.open(args.dataset/label['image']) as image:values=processor(images=image.convert('RGB'),return_tensors='pt').pixel_values.cuda().half()
        with torch.inference_mode():tokens=model.generate(values,max_new_tokens=64,num_beams=1,do_sample=False,use_cache=True)
        text=processor.batch_decode(tokens,skip_special_tokens=True)[0].strip()
        rows.append(dict(image=label['image'],expected=label['text'],predicted=text,exact=text==label['text']))
    report=dict(scope='Synthetic split reader diagnostic; not real handwriting accuracy',checkpoint=str(args.checkpoint),
        split=args.split,n=len(rows),exact=sum(row['exact'] for row in rows),
        cer=sum(edit_distance(row['predicted'],row['expected']) for row in rows)/max(1,sum(len(row['expected']) for row in rows)),rows=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print({k:v for k,v in report.items() if k!='rows'},flush=True)


if __name__=='__main__':main()
