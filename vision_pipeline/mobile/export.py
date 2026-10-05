"""Export COPIES of frozen checkpoints for Android; never save into models/.

Run tasks independently to bound host memory. Float exports are kept outside the
original checkpoint tree; quantization is opt-in and must pass a separate audit.
"""
import argparse, gc, hashlib, json, os, shutil
from pathlib import Path
os.environ.setdefault('USE_TF','0')
import numpy as np
import torch
from torch import nn
from ..common import BASE, DATA, MODELS, REPORTS, FORMS, read_json, write_json

OUT=BASE/'mobile_bundle'
def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

class Encoder(nn.Module):
    def __init__(self,m):
        super().__init__();self.encoder=m.encoder;self.projection=getattr(m,'enc_to_dec_proj',None)
        self.interpolate=getattr(m.encoder.config,'interpolate_pos_encoding',False)
    def forward(self,pixels):
        if self.interpolate:h=self.encoder(pixel_values=pixels,return_dict=False,interpolate_pos_encoding=True)[0]
        else:h=self.encoder(pixel_values=pixels,return_dict=False)[0]
        return self.projection(h) if self.projection is not None else h

class Decoder(nn.Module):
    def __init__(self,m):super().__init__();self.decoder=m.decoder
    def forward(self,ids,hidden):
        # No retained KV cache: bounded memory and a portable dynamic sequence.
        # Slower than a cache-enabled decoder; measure before promising latency.
        logits=self.decoder(input_ids=ids,encoder_hidden_states=hidden,use_cache=False,return_dict=False)[0]
        return logits[:,-1,:]

def export_ocr(route,quantize=False,source_override=None,target_root=None):
    from transformers import VisionEncoderDecoderModel,TrOCRProcessor,NougatProcessor
    folders={'latin':'trocr_latin','date':'trocr_dates','numeric':'trocr_numbers','arabic':'nougat_arabic'}
    source=Path(source_override) if source_override else MODELS/folders[route]
    before=digest(source/'model.safetensors');target=Path(target_root or OUT)/route
    if target.exists() and any(target.glob('*.onnx')):raise FileExistsError('Export destination already contains models; choose a new --output')
    target.mkdir(parents=True,exist_ok=True)
    model=VisionEncoderDecoderModel.from_pretrained(source,local_files_only=True,attn_implementation='eager').float().eval()
    processor_type=read_json(source/'preprocessor_config.json').get('image_processor_type','')
    processor=(NougatProcessor if processor_type=='NougatImageProcessor' else TrOCRProcessor).from_pretrained(source,local_files_only=True)
    from PIL import Image
    x=processor(images=Image.new('RGB',(320,48),'white'),return_tensors='pt').pixel_values
    encoder=Encoder(model).eval();decoder=Decoder(model).eval()
    with torch.no_grad(): hidden=encoder(x)
    start_id=model.generation_config.decoder_start_token_id
    if start_id is None:start_id=model.config.decoder_start_token_id
    if start_id is None:start_id=model.generation_config.bos_token_id
    ids=torch.tensor([[start_id,10,20]],dtype=torch.long)
    for name,module,args,inputs,outputs,axes in [
        ('encoder',encoder,(x,),['pixels'],['hidden'],None),
        ('decoder',decoder,(ids,hidden),['ids','hidden'],['logits'],{'ids':{1:'sequence'}})]:
        destination=target/f'{name}.onnx'
        torch.onnx.export(module,args,str(destination),input_names=inputs,output_names=outputs,dynamic_axes=axes,opset_version=17,dynamo=False,do_constant_folding=True)
        print('exported',destination,flush=True)
    tokenizer=processor.tokenizer
    # Export token pieces rather than a second tokenizer library: only decoding
    # generated token IDs is needed, not text tokenization.
    pieces=[tokenizer.convert_ids_to_tokens(i) for i in range(len(tokenizer))]
    metadata=dict(route=route,height=int(x.shape[2]),width=int(x.shape[3]),hidden_shape=list(hidden.shape),
                  start_id=start_id,eos_id=model.config.eos_token_id or model.config.decoder.eos_token_id,
                  special_ids=tokenizer.all_special_ids,pieces=pieces,tokenizer_kind='byte_bpe',
                  processor=processor.image_processor.to_dict(),max_new_tokens=64,source_sha256=before,
                  encoder='encoder.onnx',decoder='decoder.onnx',precision='FP32',cache=False)
    write_json(target/'reader.json',metadata)
    del model,encoder,decoder;gc.collect()
    if quantize:
        from onnxruntime.quantization import quantize_dynamic,QuantType
        for name in ['encoder','decoder']:
            quantize_dynamic(str(target/f'{name}.onnx'),str(target/f'{name}.int8.onnx'),weight_type=QuantType.QInt8,op_types_to_quantize=['MatMul','Gemm'],per_channel=True)
        # Candidate is NOT silently enabled; validate and select explicitly.
        metadata.update(encoder='encoder.int8.onnx',decoder='decoder.int8.onnx',precision='INT8 linear weights / mixed FP32')
        write_json(target/'reader.int8.json',metadata)
    assert digest(source/'model.safetensors')==before,'Original checkpoint changed!'
    report_path=Path(target_root)/f'export_{route}.json' if target_root else REPORTS/'mobile'/f'export_{route}.json'
    write_json(report_path,dict(source_sha256=before,checkpoint_unchanged=True,files={p.name:p.stat().st_size for p in target.iterdir()}))

def export_small():
    from ..train import classifier
    from ..grammar import RULES,ALIASES,UNKNOWN,NA
    from ultralytics import YOLO
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ['forms','script']:
        source=MODELS/f'{name}.pt';before=digest(source);state=torch.load(source,map_location='cpu',weights_only=True)
        model=classifier(len(state['classes']));model.load_state_dict(state['state_dict']);model.eval()
        torch.onnx.export(model,torch.zeros(1,3,state['size'],state['size']),str(OUT/f'{name}.onnx'),input_names=['pixels'],output_names=['logits'],opset_version=17,dynamo=False)
        write_json(OUT/f'{name}.json',dict(size=state['size'],classes=state['classes'],source_sha256=before))
        assert digest(source)==before
    for name,source in [('anchors',MODELS/'label_anchor_pilot/anchors/weights/best.pt'),('handwriting',MODELS/'long_handwriting/handwriting/weights/best.pt')]:
        before=digest(source);model=YOLO(str(source)).model.float().eval();model.fuse()
        head=model.model[-1];head.export=True;head.format='onnx';head.dynamic=False
        torch.onnx.export(model,torch.zeros(1,3,1280,1280),str(OUT/f'{name}.onnx'),input_names=['pixels'],output_names=['boxes'],opset_version=17,dynamo=False)
        assert digest(source)==before
        write_json(OUT/f'{name}.json',dict(size=1280,classes=list(model.names.values()),source_sha256=before))
    write_json(OUT/'spec.json',read_json(DATA/'label_anchor_pilot/spec.json'))
    write_json(OUT/'pairing_priors.json',read_json(DATA/'label_anchor_pilot/pairing_priors.json'))
    write_json(OUT/'grammar.json',dict(rules=RULES[FORMS[5]],aliases=ALIASES,unknown=sorted(UNKNOWN),not_applicable=sorted(NA)))

def package(precision):
    # A separate installable model directory, not embedded in an enormous APK.
    target=BASE/'mobile_install';target.mkdir(exist_ok=True)
    files=[]
    for path in OUT.glob('*'):
        if path.is_file() and path.suffix in ['.json','.onnx']:files.append((path,path.name))
    for route in ['latin','date','numeric','arabic']:
        folder=OUT/route;metadata=read_json(folder/('reader.int8.json' if precision=='int8' else 'reader.json'))
        if precision=='mixed':
            if route=='arabic':metadata=read_json(folder/'reader.int8.json')
            else:metadata.update(decoder='decoder.int8.onnx',precision='FP32 encoder / INT8 decoder linear weights; FP32 embeddings')
        dest=target/route;dest.mkdir(exist_ok=True)
        write_json(dest/'reader.json',metadata)
        for key in ['encoder','decoder']:files.append((folder/metadata[key],f'{route}/{metadata[key]}'))
    for source,relative in files:
        dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():os.link(source,dest)  # Same filesystem: no duplicate multi-GB weights.
        elif digest(dest)!=digest(source):raise RuntimeError(f'Stale package: {dest}; use a new destination/version')
    write_json(target/'manifest.json',dict(version=1,form_id='early_postnatal_newborn',precision=precision,files={str(p.relative_to(target)):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in target.rglob('*') if p.is_file() and p.name!='manifest.json'}))
    print('Install bundle:',target,flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('task',choices=['small','latin','date','numeric','arabic','package']);ap.add_argument('--int8',action='store_true');ap.add_argument('--mixed',action='store_true');ap.add_argument('--checkpoint',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args();torch.set_num_threads(4)
    if a.task in ('small','package') and (a.checkpoint or a.output):ap.error('--checkpoint and --output are for OCR exports')
    if a.task=='small':export_small()
    elif a.task=='package':package('mixed' if a.mixed else 'int8' if a.int8 else 'fp32')
    else:export_ocr(a.task,a.int8,a.checkpoint,a.output)
if __name__=='__main__':main()
