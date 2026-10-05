"""Compare graph-fusion levels on identical, captured Android reader inputs."""
import argparse
import gc
import io
import json
import tarfile
import time
from pathlib import Path
import numpy as np
import onnxruntime as ort
from PIL import Image


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',type=Path,required=True)
    ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--route',default='latin')
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--limit',type=int,default=6)
    args=ap.parse_args();config=json.loads((args.pack/args.route/'reader.json').read_text())
    inputs=[]
    with tarfile.open(args.capture/'crops.tar') as archive:
        for member in archive.getmembers():
            if not member.name.endswith('_'+args.route+'_input.png'):continue
            with Image.open(io.BytesIO(archive.extractfile(member).read())) as image:
                pixels=np.asarray(image.convert('RGB'),dtype=np.float32)/255
            pixels=(pixels-np.array(config['processor']['image_mean'],np.float32))/np.array(config['processor']['image_std'],np.float32)
            inputs.append((member.name,pixels.transpose(2,0,1)[None]))
            if len(inputs)>=args.limit:break
    report=dict(scope='Desktop CPU graph-fusion diagnostic; not phone timing',route=args.route,levels={})
    for level in ['basic','extended','all']:
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
        options.graph_optimization_level=getattr(ort.GraphOptimizationLevel,'ORT_ENABLE_'+level.upper())
        started=time.perf_counter()
        encoder=ort.InferenceSession(str(args.pack/args.route/config['encoder']),options,providers=['CPUExecutionProvider'])
        decoder=ort.InferenceSession(str(args.pack/args.route/config['decoder']),options,providers=['CPUExecutionProvider'])
        rows=[];load_seconds=time.perf_counter()-started
        for name,pixels in inputs:
            started=time.perf_counter();hidden=encoder.run(None,{'pixels':pixels})[0]
            encoded=time.perf_counter();tokens=[];ids=np.array([[config['start_id']]],np.int64)
            for _ in range(config['max_new_tokens']):
                logits=decoder.run(None,{'ids':ids,'hidden':hidden})[0]
                token=int(logits.argmax());tokens.append(token)
                if token==config['eos_id']:break
                ids=np.concatenate([ids,np.array([[token]],np.int64)],axis=1)
            rows.append(dict(input=name,tokens=tokens,encoder_seconds=encoded-started,decoder_seconds=time.perf_counter()-encoded))
        report['levels'][level]=dict(load_seconds=load_seconds,rows=rows)
        print(level,load_seconds,sum(row['encoder_seconds']+row['decoder_seconds'] for row in rows),flush=True)
        del encoder,decoder;gc.collect()
    base=report['levels']['basic']['rows']
    report['token_identical']={level:all(a['tokens']==b['tokens'] for a,b in zip(base,data['rows'])) for level,data in report['levels'].items()}
    args.output.write_text(json.dumps(report,indent=2));print(report['token_identical'],flush=True)


if __name__=='__main__':main()
