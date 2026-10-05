"""Read-only reader comparison on frozen organizer crops; never used for training labels."""
import argparse
import json
import os
import re
from pathlib import Path
os.environ.setdefault('USE_TF','0')
import torch
from PIL import Image,ImageOps
from transformers import TrOCRProcessor,VisionEncoderDecoderModel
from .common import ROOT,BASE,DATA
from .label_anchor_pilot.evaluate import normalized
from .date_ocr.train import edit_distance


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--pages',type=int,default=8)
    args=parser.parse_args();torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.15)
    processor=TrOCRProcessor.from_pretrained(args.checkpoint,local_files_only=True)
    model=VisionEncoderDecoderModel.from_pretrained(args.checkpoint,local_files_only=True).cuda().half().eval()
    refs=[json.loads(line) for line in (DATA/'organizer_test/labels.jsonl').read_text().splitlines()]
    rows=[]
    for ref in refs:
        if ref['pdf_page']>args.pages:continue
        pred=json.loads((BASE/'outputs/all_forms'/f'page_{ref["pdf_page"]:02d}'/'prediction.json').read_text())
        spec=json.loads((DATA/'all_forms'/ref['form_id']/'spec.json').read_text())
        for key,label in ref['fields'].items():
            if not(label.get('score_eligible') and label['kind']=='text' and label['status']=='KNOWN'):continue
            binding=spec['bindings'].get(key,{})
            if binding.get('schema',{}).get('type') in ('integer','double','date') or key=='record_code':continue
            field=pred['fields'].get(key,{})
            latin=next((raw for raw in field.get('raw_candidates',[]) if raw.get('script')=='latin'),None)
            if not latin:continue
            # Stable local path rather than a machine-specific debug directory saved in JSON.
            path=BASE/'outputs/all_forms'/f'page_{ref["pdf_page"]:02d}'/'ocr'/re.sub('[^A-Za-z0-9_-]','_',key)/'latin/crop_before_processor.png'
            if not path.is_file():continue
            with Image.open(path) as image:
                if getattr(processor.image_processor,'sanad_fit',False):
                    size=processor.image_processor.size;image=ImageOps.pad(image.convert('RGB'),(size['width'],size['height']),color='white',method=Image.Resampling.BILINEAR)
                values=processor(images=image.convert('RGB'),return_tensors='pt').pixel_values.cuda().half()
            geometry={'interpolate_pos_encoding':True} if getattr(model.config.encoder,'interpolate_pos_encoding',False) else {}
            with torch.inference_mode():tokens=model.generate(values,max_new_tokens=64,num_beams=1,do_sample=False,use_cache=True,**geometry)
            text=processor.batch_decode(tokens,skip_special_tokens=True)[0].strip();expected=label['raw_text'].strip()
            row=dict(page=ref['pdf_page'],field=key,expected=expected,baseline=latin['text'],candidate=text,
                     baseline_match=normalized(latin['text'])==normalized(expected),candidate_match=normalized(text)==normalized(expected))
            rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    report=dict(scope='Organizer development diagnostic on frozen PC Latin-reader crops; reference PDF glyph text; excludes fields without Latin crops',
                checkpoint=str(args.checkpoint),n=len(rows),baseline_normalized=sum(r['baseline_match'] for r in rows),
                candidate_normalized=sum(r['candidate_match'] for r in rows),
                candidate_cer=sum(edit_distance(r['candidate'],r['expected']) for r in rows)/max(1,sum(len(r['expected']) for r in rows)),rows=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print({k:v for k,v in report.items() if k!='rows'},flush=True)


if __name__=='__main__':main()
