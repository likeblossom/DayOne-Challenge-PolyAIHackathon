"""Read-only checkpoint/export comparison on stored exact OCR inputs.

This measures desktop CPU export behavior, never claims Android latency or RAM.
"""
import argparse,gc,json,time,resource
import numpy as np
import onnxruntime as ort
import torch
from ..common import BASE,REPORTS,write_json,read_json
from .export import OUT

def session(path):
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
    return ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])

def decode(encoder,decoder,pixels,config):
    hidden=encoder.run(None,{'pixels':pixels})[0];ids=np.array([[config['start_id']]],dtype=np.int64);tokens=[]
    for _ in range(64):
        logits=decoder.run(None,{'ids':ids,'hidden':hidden})[0];token=int(logits.argmax(-1)[0]);tokens.append(token)
        if token==config['eos_id']:break
        ids=np.concatenate([ids,np.array([[token]],dtype=np.int64)],axis=1)
    return tokens

def main():
    ap=argparse.ArgumentParser();ap.add_argument('route',choices=['latin','date','numeric','arabic']);ap.add_argument('--limit',type=int,default=12);ap.add_argument('--precision',choices=['fp32','int8','mixed','selective'],default='int8');a=ap.parse_args()
    from transformers import AutoTokenizer
    names={'latin':'trocr_latin','date':'trocr_dates','numeric':'trocr_numbers','arabic':'nougat_arabic'}
    tokenizer=AutoTokenizer.from_pretrained(BASE/'models'/names[a.route],local_files_only=True)
    folder=OUT/a.route;config=read_json(folder/('reader.int8.json' if a.precision=='int8' else 'reader.json'))
    if a.precision=='mixed':config['decoder']='decoder.int8.onnx'
    if a.precision=='selective':config['decoder']='decoder.selective.onnx'
    enc=session(folder/config['encoder']);dec=session(folder/config['decoder']);results=[]
    paths=sorted((BASE/'outputs/unit_grammar').glob(f'page_*/relative/ocr/*/{a.route}/ocr_output.json'))
    if not paths:paths=sorted((BASE/'outputs/resource_profile').glob(f'page_*/ocr/*/{a.route}/ocr_output.json'))
    seen=set()
    for path in paths:
        ref=read_json(path);pixelpath=path.with_name('exact_pixel_values.pt');pixels=torch.load(pixelpath,map_location='cpu',weights_only=True).float().numpy();key=(pixels.tobytes(),ref['text'])
        if key in seen:continue
        seen.add(key);start=time.perf_counter();ids=decode(enc,dec,pixels,config);text=tokenizer.decode(ids,skip_special_tokens=True).strip()
        row=dict(source=str(path.relative_to(BASE)),reference_raw=ref['text'],export_raw=text,raw_equal=text==ref['text'],seconds=time.perf_counter()-start,token_ids=ids)
        results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
        if len(results)>=a.limit:break
    report=dict(route=a.route,precision=a.precision,n=len(results),raw_equal=sum(r['raw_equal'] for r in results),results=results,peak_process_rss_gb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024/1e9,scope='Desktop ONNX CPU on saved normalized tensors; not Android preprocessing, not organizer ground-truth accuracy. Agreement is with original FP16 outputs.',model_bytes=sum((folder/config[k]).stat().st_size for k in ['encoder','decoder']))
    write_json(REPORTS/'mobile'/f'{a.route}_{a.precision}_validation.json',report)
    print('agreement',report['raw_equal'],'/',report['n'],flush=True)
if __name__=='__main__':main()
