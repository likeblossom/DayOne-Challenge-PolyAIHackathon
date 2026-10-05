"""Build a new candidate pack without copying or modifying frozen base checkpoints."""
import argparse
import json
from pathlib import Path
import torch
from ..common import BASE
from ..train import classifier
from .export import digest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--base-pack',type=Path,help='Existing immutable pack to inherit; defaults to the original frozen pack')
    parser.add_argument('--forms',type=Path);parser.add_argument('--script',type=Path)
    parser.add_argument('--latin',type=Path,help='Export directory containing reader.json and ONNX files')
    parser.add_argument('--arabic',type=Path,help='Export directory containing reader.json and ONNX files')
    parser.add_argument('--numeric',type=Path,help='Separately validated numeric reader export; original checkpoint remains unchanged')
    parser.add_argument('--optimization',choices=['basic','extended','all'],default='basic')
    parser.add_argument('--anchors-root',type=Path,help='Completed detector refinements; promote only if synthetic validation improves')
    parser.add_argument('--retain-base-anchors',type=int,nargs='*',default=[],help='Keep original detectors rejected by downstream development regression tests')
    parser.add_argument('--strip-edge-rules',action='store_true',help='Conservative full-span crop-edge rule trimming; requires separate parity audit')
    parser.add_argument('--reject-printed-centers',action='store_true',help='Exclude handwriting detections centered inside confident printed-label detections')
    parser.add_argument('--adaptive-numeric-crop',action='store_true',help='Expand numeric crops only when side-boundary ink suggests clipping; experimental until phone regression-tested')
    args=parser.parse_args();torch.set_num_threads(2)
    if args.output.exists():raise FileExistsError('Candidate destination must be new')
    args.output.mkdir(parents=True)
    base=args.base_pack or BASE/'mobile_install_all_forms';manifest=json.loads((base/'manifest.json').read_text())
    replacements={}
    detector_selection={}
    if args.anchors_root:
        from ..common import FORMS,REPORTS
        from ..all_forms.mobile import detector
        for number,form in enumerate(FORMS,1):
            folder=args.anchors_root/form
            if not (folder/'audit.json').is_file():continue
            candidate=json.loads((folder/'audit.json').read_text())
            previous=max(json.loads(path.read_text())['validation_metrics']['metrics/mAP50-95(B)']
                         for path in (REPORTS/'all_forms').glob(form+'*training.json'))
            score=candidate['validation']['metrics/mAP50-95(B)']
            promote=score>previous and number not in args.retain_base_anchors
            detector_selection[form]=dict(previous_map=previous,candidate_map=score,promoted=promote)
            if number in args.retain_base_anchors:detector_selection[form]['deployment_gate']='Retained baseline after organizer development regression; not a sealed test'
            if not promote:continue
            relative='forms_config/'+form+'/anchors';target=args.output/relative;target.parent.mkdir(parents=True,exist_ok=True)
            detector(folder/'weights/best.pt',target)
            old_config=json.loads((base/(relative+'.json')).read_text())
            new_config=json.loads(target.with_suffix('.json').read_text())
            if old_config['classes']!=new_config['classes']:raise ValueError('Detector classes changed: '+form)
            for suffix in ['.onnx','.json']:replacements[relative+suffix]=target.with_suffix(suffix)
    for name in ['forms','script']:
        checkpoint=getattr(args,name)
        if checkpoint:
            state=torch.load(checkpoint,map_location='cpu',weights_only=True)
            model=classifier(len(state['classes']));model.load_state_dict(state['state_dict']);model.eval()
            args.output.mkdir(parents=True,exist_ok=True)
            target=args.output/(name+'.onnx')
            torch.onnx.export(model,torch.zeros(1,3,state['size'],state['size']),str(target),
                              input_names=['pixels'],output_names=['logits'],opset_version=17,dynamo=False)
            (args.output/(name+'.json')).write_text(json.dumps(dict(size=state['size'],classes=state['classes'],source_sha256=digest(checkpoint)),indent=2))
            replacements.update({name+'.onnx':target,name+'.json':args.output/(name+'.json')})
    for route in ['latin','arabic','numeric']:
        export=getattr(args,route)
        if not export:continue
        config=json.loads((export/'reader.json').read_text())
        config.update(decoder='decoder.int8.onnx',precision='FP32 encoder / INT8 decoder linear weights; FP32 embeddings')
        folder=args.output/route;folder.mkdir(parents=True,exist_ok=True)
        (folder/'reader.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
        replacements[route+'/reader.json']=folder/'reader.json'
        # Remove the previous reader's model filenames if the architecture changed.
        for name in list(manifest['files']):
            if name.startswith(route+'/') and name.endswith('.onnx'):del manifest['files'][name]
        for key in ['encoder','decoder']:
            source=(export/config[key]).resolve();target=folder/config[key];target.symlink_to(source)
            replacements[route+'/'+config[key]]=target
    if args.strip_edge_rules:
        # Arabic has a different preprocessing path; enable only audited readers.
        for route in ['latin','date','numeric']:
            name=route+'/reader.json'
            config=json.loads((replacements.get(name) or base/name).read_text())
            config['strip_edge_rules']=True
            target=args.output/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(config,ensure_ascii=False,indent=2));replacements[name]=target
    for name in manifest['files']:
        if name in replacements:continue
        target=args.output/name;target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to((base/name).resolve())
    for name,path in replacements.items():manifest['files'][name]=dict(bytes=path.stat().st_size,sha256=digest(path))
    manifest['revision']=args.output.name
    manifest['runtime']=dict(optimization=args.optimization,threads=2,reject_printed_centers=args.reject_printed_centers)
    if args.adaptive_numeric_crop:manifest['runtime']['adaptive_numeric_crop']=True
    if detector_selection:manifest['detector_selection']=detector_selection
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(pack=str(args.output),manifest_sha256=digest(args.output/'manifest.json'),replaced_files=list(replacements))),flush=True)


if __name__=='__main__':main()
