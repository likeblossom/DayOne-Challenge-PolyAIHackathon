"""Eight-class routing to form-specific anchors and a shared handwriting detector."""
import argparse
from ..common import *
from ..infer import Predictor
from ..label_anchor_pilot.infer import Pilot
from .checkpoints import anchor_checkpoint

class AllForms:
    def __init__(self,save_tensors=False):
        self.classifier=Predictor(MODELS/'forms.pt');self.pilot=None;self.save_tensors=save_tensors
    def extract(self,image,out,form_override=None,mode='relative'):
        prediction=self.classifier(Image.open(image).convert('RGB'))
        form=form_override or FORMS[int(prediction['label'])]
        if self.pilot is None or self.pilot.form!=form:
            ocr=self.pilot.ocr if self.pilot else None
            self.pilot=Pilot(date_expert=True,numeric_expert=True,work=DATA/'all_forms'/form,anchor_weights=anchor_checkpoint(form),handwriting_weights=anchor_checkpoint('handwriting'),save_tensors=self.save_tensors,square_input=True)
            if ocr:self.pilot.ocr=ocr
        result=self.pilot.extract(image,out,mode)
        result.update(form_prediction=prediction,form_override=form_override,form_routing_review_required=prediction['confidence']<.75)
        for f in result['fields'].values():
            f['confidence']=min(f['confidence'],prediction['confidence'])
            if f.get('confidence_components'):f['confidence_components']['form']=prediction['confidence']
            if prediction['confidence']<.75:f['status']='NEEDS_REVIEW';f['issues'].append('UNCERTAIN_FORM_CLASSIFICATION')
        write_json(Path(out)/'prediction.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('image',type=Path);p.add_argument('--output',type=Path,default=BASE/'outputs/all_forms/demo');p.add_argument('--save-tensors',action='store_true');a=p.parse_args()
    print(AllForms(a.save_tensors).extract(a.image,a.output)['form_id'])
if __name__=='__main__':main()
