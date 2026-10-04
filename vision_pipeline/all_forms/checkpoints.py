from ..common import MODELS,REPORTS,read_json

def anchor_checkpoint(form):
    """Choose only by held-out synthetic validation, never organizer performance."""
    candidates=[]
    for suffix in ['', '_refined','_final']:
        report=REPORTS/'all_forms'/(form+suffix+'_training.json')
        if report.exists():
            r=read_json(report);candidates.append((r['validation_metrics']['metrics/mAP50-95(B)'],r['best_checkpoint']))
    if not candidates:raise FileNotFoundError('No completed anchor training for '+form)
    return max(candidates)[1]
