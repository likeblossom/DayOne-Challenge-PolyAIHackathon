"""Local-only ArTrOCR probe with its documented line-shaped input and tokenizer."""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('USE_TF','0')
import torch
from PIL import Image
from transformers import VisionEncoderDecoderModel,ViTImageProcessor,PreTrainedTokenizerFast
from .date_ocr.train import edit_distance


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--checkpoint',type=Path,required=True)
    ap.add_argument('--dataset',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--limit',type=int,default=100);args=ap.parse_args();torch.set_num_threads(2)
    processor=ViTImageProcessor(**json.loads((args.checkpoint/'processor_config.json').read_text())['image_processor'])
    tokenizer=PreTrainedTokenizerFast(tokenizer_file=str(args.checkpoint/'tokenizer.json'),
        bos_token='<s>',eos_token='</s>',pad_token='<pad>',unk_token='<unk>',mask_token='<mask>')
    model=VisionEncoderDecoderModel.from_pretrained(args.checkpoint,local_files_only=True,use_safetensors=True).eval()
    rows=[json.loads(line) for line in (args.dataset/'labels.jsonl').read_text().splitlines() if json.loads(line)['split']=='val']
    if len(rows)>args.limit:rows=[rows[i*len(rows)//args.limit] for i in range(args.limit)]
    results=[]
    for row in rows:
        with Image.open(args.dataset/row['image']) as source:
            image=source.convert('RGB');width=min(512,max(1,int(image.width*102/image.height)))
            image=image.resize((width,102),Image.Resampling.LANCZOS)
            canvas=Image.new('RGB',(512,102),'white');canvas.paste(image,(0,0))
        pixels=processor(images=canvas,return_tensors='pt').pixel_values
        with torch.inference_mode():tokens=model.generate(pixels,max_new_tokens=64,num_beams=1,do_sample=False,use_cache=True,interpolate_pos_encoding=True)
        text=tokenizer.batch_decode(tokens,skip_special_tokens=True)[0].strip()
        results.append(dict(expected=row['text'],predicted=text,image=row['image'],exact=text==row['text']))
        if len(results)%10==0:print(len(results),sum(r['exact'] for r in results),flush=True)
    report=dict(scope='Synthetic held-out font probe; not real Arabic handwriting accuracy',checkpoint=str(args.checkpoint),
        preprocessing='Resize to height 102, width capped at 512; left-aligned white canvas; Lanczos; ViT position interpolation',
        n=len(results),exact=sum(r['exact'] for r in results),cer=sum(edit_distance(r['predicted'],r['expected']) for r in results)/max(1,sum(len(r['expected']) for r in results)),rows=results)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2));print({k:v for k,v in report.items() if k!='rows'})


if __name__=='__main__':main()
