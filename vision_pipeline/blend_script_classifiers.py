"""Validation-selected weight interpolation of compatible script refinements."""
import argparse
import hashlib
import json
from pathlib import Path
import torch
from torch.utils.data import DataLoader
from .refine_form_classifier import Scripts
from .train import classifier,evaluate


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Use a new experiment directory')
    args.output.mkdir(parents=True);torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.15)
    a=torch.load(args.baseline,map_location='cpu',weights_only=True);b=torch.load(args.candidate,map_location='cpu',weights_only=True)
    assert a['classes']==b['classes'] and a['size']==b['size']
    loaders={split:DataLoader(Scripts(split,a['size']),batch_size=32,num_workers=2) for split in ['val','test']}
    report=dict(organizer_used=False,selection='Original font-disjoint synthetic validation accuracy; loss breaks ties',
        sources=[dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in [args.baseline,args.candidate]],variants=[])
    best=(-1.,-float('inf'));best_state=None
    for alpha in [0.,.25,.5,.75,1.]:
        weights={key:(1-alpha)*value+alpha*b['state_dict'][key] if value.is_floating_point() else value for key,value in a['state_dict'].items()}
        model=classifier(len(a['classes'])).cuda();model.load_state_dict(weights)
        metrics=evaluate(model,loaders['val'],'cuda',len(a['classes']));rank=(metrics['accuracy'],-metrics['loss'])
        report['variants'].append(dict(alpha=alpha,validation=metrics));print(report['variants'][-1],flush=True)
        if rank>best:best=rank;best_state=weights;report['selected_alpha']=alpha
        del model
    model=classifier(len(a['classes'])).cuda();model.load_state_dict(best_state)
    report['test']=evaluate(model,loaders['test'],'cuda',len(a['classes']))
    state=dict(a,state_dict=best_state,training_source='Synthetic-only interpolation; see experiment report',interpolation_alpha=report['selected_alpha'])
    torch.save(state,args.output/'best.pt')
    (args.output/'report.json').write_text(json.dumps(report,indent=2));print('SELECTED',report['selected_alpha'],report['test'],flush=True)


if __name__=='__main__':main()
