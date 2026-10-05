"""Evaluate conservative edge-rule trimming on captured numeric reader crops."""
import argparse
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
import numpy as np
import onnxruntime as ort
from PIL import Image
from transformers import AutoTokenizer
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from vision_pipeline.grammar import parse
from benchmark_android import normalized
from vision_pipeline.label_anchor_pilot.common import frame


def expanded_crop(page,quad,margin):
    import cv2
    center,u,v,width,height=frame(quad)
    width+=2*max(4,height*margin);height+=2*max(3,height*.12)
    size=(max(8,min(round(width),page.width*2)),max(8,min(round(height),page.height*2)))
    source=np.float32([center-u*width/2-v*height/2,center+u*width/2-v*height/2,
                      center+u*width/2+v*height/2,center-u*width/2+v*height/2])
    matrix=cv2.getPerspectiveTransform(source,np.float32([[0,0],[size[0]-1,0],[size[0]-1,size[1]-1],[0,size[1]-1]]))
    return Image.fromarray(cv2.warpPerspective(np.asarray(page),matrix,size,borderValue=(255,255,255)))


def leaves(node,path=''):
    if isinstance(node,list):
        for i,item in enumerate(node):yield from leaves(item,path+f'[{i}]')
    elif isinstance(node,dict):
        if 'status' in node:yield path,node
        else:
            for key,value in node.items():yield from leaves(value,path+'.'+key if path else key)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--pages',default='3,11');ap.add_argument('--pack',type=Path,default=ROOT/'vision_pipeline/mobile_install_all_forms')
    ap.add_argument('--route',choices=['numeric','latin','date'],default='numeric')
    ap.add_argument('--checkpoint',type=Path,help='Evaluate a separate PyTorch reader on every cleaned crop, not only changed crops')
    ap.add_argument('--rerun-all',action='store_true',help='Decode unchanged crops too when comparing an exported reader')
    ap.add_argument('--horizontal-margin',type=float,help='PC diagnostic: recreate captured quads with this horizontal padding fraction of line height')
    args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Use a new diagnostic output; preserve prior evidence')
    args.output.mkdir(parents=True)
    refs={r['pdf_page']:r for r in map(json.loads,(ROOT/'data/processed/organizer_test_v3/labels.jsonl').read_text().splitlines())}
    rows=[];commands=[]
    numbers=sorted(int(path.name.removeprefix('page_')) for path in args.capture.glob('page_*') if (path/'result.json').is_file()) if args.pages=='all' else list(map(int,args.pages.split(',')))
    for number in numbers:
        folder=args.capture/f'page_{number:02d}';result=json.loads((folder/'result.json').read_text());truth=refs[number]
        page=None
        if args.horizontal_margin is not None:
            if not 0<=args.horizontal_margin<=1:raise ValueError('Margin must be between zero and one')
            with Image.open(ROOT/truth['image']) as original:
                page=original.convert('RGB').resize((result['metadata']['decoded_page_width'],result['metadata']['decoded_page_height']),Image.Resampling.BILINEAR)
        with tarfile.open(folder/'crops.tar') as archive:
            for key,field in leaves(result['fields']):
                label=truth['fields'].get(key,{})
                if field.get('ocr',{}).get('model')!=args.route or not label.get('score_eligible') or label.get('status')!='KNOWN':continue
                name=re.sub('[^A-Za-z0-9_-]','_',key)+'.png'
                with Image.open(io.BytesIO(archive.extractfile('./'+name).read())) as source:image=source.convert('RGB')
                if page is not None:image=expanded_crop(page,field['crop_quad'],args.horizontal_margin)
                path=args.output/f'{number}_{name}';image.save(path)
                commands.append(str(path.resolve())+'\trules')
                rows.append(dict(page=number,form=truth['form_id'],field=key,expected=label['value'],baseline=field['value'],baseline_raw=field['raw_text'],crop=str(path)))
    with tempfile.TemporaryDirectory(prefix='sanad-edge-rules-') as temporary:
        source=ROOT/'android-app/app/src/main/java/org/dayone/midwife'
        subprocess.run(['javac','-d',temporary,str(source/'CheckboxReader.java'),str(source/'EdgeRuleCrop.java'),str(ROOT/'android-app/tools/CheckboxDiagnostic.java')],check=True)
        output=subprocess.run(['java','-cp',temporary,'CheckboxDiagnostic'],input='\n'.join(commands)+'\n',text=True,capture_output=True,check=True).stdout
    bounds=list(map(json.loads,output.splitlines()));assert len(bounds)==len(rows)
    config=json.loads((args.pack/args.route/'reader.json').read_text());options=ort.SessionOptions()
    options.intra_op_num_threads=2;options.inter_op_num_threads=1;options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
    options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    if args.checkpoint:
        import torch
        from transformers import TrOCRProcessor,VisionEncoderDecoderModel
        torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.25)
        processor=TrOCRProcessor.from_pretrained(args.checkpoint,local_files_only=True)
        model=VisionEncoderDecoderModel.from_pretrained(args.checkpoint,local_files_only=True).cuda().float().eval()
    else:
        encoder=ort.InferenceSession(str(args.pack/args.route/config['encoder']),options,providers=['CPUExecutionProvider'])
        decoder=ort.InferenceSession(str(args.pack/args.route/config['decoder']),options,providers=['CPUExecutionProvider'])
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'vision_pipeline/models'/dict(numeric='trocr_numbers',latin='trocr_latin',date='trocr_dates')[args.route],local_files_only=True)
    for row,box in zip(rows,bounds):
        with Image.open(row['crop']) as image:
            row['trim_bounds']=box;row['changed']=box!=[0,0,*image.size]
            if not row['changed'] and not args.checkpoint and not args.rerun_all and args.horizontal_margin is None:
                row.update(candidate=row['baseline'],candidate_raw=row['baseline_raw']);continue
            cleaned=image.crop(box);cleaned.save(Path(row['crop']).with_name(Path(row['crop']).stem+'_cleaned.png'))
            if args.checkpoint:
                values=processor(images=cleaned.convert('RGB'),return_tensors='pt').pixel_values.cuda()
                with torch.inference_mode():generated=model.generate(values,max_new_tokens=64,num_beams=1,do_sample=False,use_cache=True)
                text=processor.batch_decode(generated,skip_special_tokens=True)[0].strip()
                parsed=parse(row['form'],row['field'],text)
                row.update(candidate=parsed['value'],candidate_raw=text,issues=parsed['issues'])
                print(row['page'],row['field'],row['baseline_raw'],'->',text,flush=True)
                continue
            image=cleaned.resize((config['width'],config['height']),Image.Resampling.BILINEAR)
        pixels=np.asarray(image,np.float32)/255
        pixels=(pixels-np.array(config['processor']['image_mean'],np.float32))/np.array(config['processor']['image_std'],np.float32)
        hidden=encoder.run(None,{'pixels':pixels.transpose(2,0,1)[None]})[0];ids=np.array([[config['start_id']]],np.int64);tokens=[]
        for _ in range(config['max_new_tokens']):
            logits=decoder.run(None,{'ids':ids,'hidden':hidden})[0];token=int(logits.argmax());tokens.append(token)
            if token==config['eos_id']:break
            ids=np.concatenate([ids,np.array([[token]],np.int64)],axis=1)
        text=tokenizer.decode(tokens,skip_special_tokens=True).strip();parsed=parse(row['form'],row['field'],text)
        row.update(candidate=parsed['value'],candidate_raw=text,issues=parsed['issues'])
        print(row['page'],row['field'],row['baseline_raw'],'->',text,flush=True)
    report=dict(scope='PC ONNX diagnostic on captured phone crops; unchanged crops reuse phone result; not Android end-to-end accuracy',route=args.route,n=len(rows),
        normalization='NFKD casefold alphanumeric for strings; exact canonical comparison for numbers and booleans',
        changed=sum(row['changed'] for row in rows),baseline_correct=sum(normalized(row['baseline'])==normalized(row['expected']) for row in rows),
        candidate_correct=sum(normalized(row['candidate'])==normalized(row['expected']) for row in rows),rows=rows)
    if args.checkpoint:
        report.update(scope='PC FP32 PyTorch reader diagnostic on captured phone crops, all crops decoded; not Android end-to-end accuracy',checkpoint=str(args.checkpoint.resolve()))
    elif args.rerun_all:
        report.update(scope='PC ONNX reader diagnostic on captured phone crops, all crops decoded after edge cleanup; not Android end-to-end accuracy',pack=str(args.pack.resolve()))
    if args.horizontal_margin is not None:
        report.update(scope='PC reconstructed crops using captured phone quads and resized source pages; interpolation differs from Android; not Android end-to-end accuracy',horizontal_margin=args.horizontal_margin)
    (args.output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print({k:v for k,v in report.items() if k!='rows'})


if __name__=='__main__':main()
