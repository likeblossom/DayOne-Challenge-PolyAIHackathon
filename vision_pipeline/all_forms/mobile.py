"""New eight-form pack, reusing frozen OCR exports by hardlink (no duplication)."""
import os
import torch
from ultralytics import YOLO
from ..common import *
from ..grammar import RULES,ALIASES,UNKNOWN,NA
from ..mobile.export import digest
from .checkpoints import anchor_checkpoint

TARGET=BASE/'mobile_install_all_forms'
def detector(source,dest):
    before=digest(source);model=YOLO(str(source)).model.float().eval();model.fuse()
    head=model.model[-1];head.export=True;head.format='onnx';head.dynamic=False
    torch.onnx.export(model,torch.zeros(1,3,1280,1280),str(dest.with_suffix('.onnx')),input_names=['pixels'],output_names=['boxes'],opset_version=17,dynamo=False)
    write_json(dest.with_suffix('.json'),dict(size=1280,classes=list(model.names.values()),max_det=600,source_sha256=before))
    assert digest(source)==before

def main():
    torch.set_num_threads(4);TARGET.mkdir(exist_ok=True);old=BASE/'mobile_install'
    for p in old.rglob('*'):
        rel=p.relative_to(old)
        if not p.is_file() or (len(rel.parts)==1 and p.stem not in ['forms','script']):continue
        dst=TARGET/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists():
            if p.suffix=='.json':write_json(dst,read_json(p))
            else:os.link(p,dst)
    routing={}
    for i,form in enumerate(FORMS):
        folder=TARGET/'forms_config'/form;folder.mkdir(parents=True,exist_ok=True)
        for name in ['spec.json','pairing_priors.json']:write_json(folder/name,read_json(DATA/'all_forms'/form/name))
        write_json(folder/'grammar.json',dict(rules=RULES[form],aliases=ALIASES,unknown=sorted(UNKNOWN),not_applicable=sorted(NA)))
        detector(Path(anchor_checkpoint(form)),folder/'anchors')
        routing[str(i)]=dict(form_id=form[3:],folder=str(folder.relative_to(TARGET)))
    detector(Path(anchor_checkpoint('handwriting')),TARGET/'handwriting')
    write_json(TARGET/'routing.json',routing)
    files={str(p.relative_to(TARGET)):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in TARGET.rglob('*') if p.is_file() and p.name!='manifest.json'}
    write_json(TARGET/'manifest.json',dict(version=1,scope='all_eight_forms',form_ids=[f[3:] for f in FORMS],precision='mixed',files=files))
    write_json(REPORTS/'all_forms/mobile_pack.json',dict(directory=str(TARGET),total_bytes=sum(p['bytes'] for p in files.values()),form_count=8,original_ocr_retrained=False,phone_benchmark=False))
    print(TARGET,flush=True)
if __name__=='__main__':main()
