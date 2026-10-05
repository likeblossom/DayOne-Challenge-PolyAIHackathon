"""Audit captured Android crops/preprocessor RGB and decoder tokens against desktop ONNX."""
import argparse
import io
import json
import os
import re
import tarfile
from pathlib import Path
os.environ.setdefault('USE_TF','0')
import numpy as np
import onnxruntime as ort
from PIL import Image
from transformers import TrOCRProcessor,NougatProcessor

ROOT=Path(__file__).resolve().parents[2]
PACK=ROOT/'vision_pipeline/mobile_install_all_forms'


def walk(node,path=''):
    if isinstance(node,list):
        for index,item in enumerate(node):yield from walk(item,f'{path}[{index}]')
    elif isinstance(node,dict):
        if 'crop_quad' in node:yield path,node
        elif 'status' not in node:
            for key,value in node.items():yield from walk(value,f'{path}.{key}' if path else key)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('capture',type=Path)
    parser.add_argument('--decode',action='store_true');args=parser.parse_args()
    fields=list(walk(json.loads((args.capture/'result.json').read_text())['fields']))
    archive=tarfile.open(args.capture/'crops.tar');reports=[]
    names={'latin':'trocr_latin','numeric':'trocr_numbers','date':'trocr_dates','arabic':'nougat_arabic'}
    for route,checkpoint in names.items():
        selected=[(key,field,raw) for key,field in fields for raw in field['raw_candidates'] if raw['model']==route]
        if not selected:continue
        processor=(NougatProcessor if route=='arabic' else TrOCRProcessor).from_pretrained(ROOT/'vision_pipeline/models'/checkpoint,local_files_only=True)
        config=json.loads((PACK/route/'reader.json').read_text())
        if args.decode:
            options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
            options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
            encoder=ort.InferenceSession(str(PACK/route/config['encoder']),sess_options=options,providers=['CPUExecutionProvider'])
            decoder=ort.InferenceSession(str(PACK/route/config['decoder']),sess_options=options,providers=['CPUExecutionProvider'])
        for key,field,raw in selected:
            name=re.sub('[^A-Za-z0-9_-]','_',key)
            crop=Image.open(io.BytesIO(archive.extractfile('./'+name+'.png').read())).convert('RGB')
            phone=Image.open(io.BytesIO(archive.extractfile('./'+name+'_'+route+'_input.png').read())).convert('RGB')
            pixels=processor(images=crop,return_tensors='np').pixel_values
            proc=config['processor'];mean=np.array(proc['image_mean']);std=np.array(proc['image_std'])
            expected=np.clip(np.rint((pixels[0].transpose(1,2,0)*std+mean)*255),0,255).astype('uint8')
            report=dict(field=key,route=route,pixel_mae=float(np.abs(np.array(phone,dtype=float)-expected).mean()),phone_text=raw['text'])
            Image.fromarray(expected).save(args.capture/(name+'_'+route+'_pc_input.png'))
            if args.decode:
                # Exact captured Android RGB, not the PC's possibly different preprocessing.
                x=((np.array(phone,dtype=np.float32)/255-np.array(mean,dtype=np.float32))/np.array(std,dtype=np.float32)).transpose(2,0,1)[None]
                hidden=encoder.run(None,{'pixels':x})[0];ids=np.array([[config['start_id']]],dtype=np.int64);tokens=[]
                for _ in range(config['max_new_tokens']):
                    logits=decoder.run(None,{'ids':ids,'hidden':hidden})[0];token=int(logits.argmax(-1)[0]);tokens.append(token)
                    if token==config['eos_id']:break
                    ids=np.concatenate([ids,np.array([[token]],dtype=np.int64)],axis=1)
                report.update(desktop_text=processor.tokenizer.decode(tokens,skip_special_tokens=True).strip(),
                              tokens_equal=tokens==raw['token_ids'])
            reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
        if args.decode:del encoder,decoder
    (args.capture/'ocr_parity.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
