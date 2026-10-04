"""Offline-only pretrained transformer OCR; no remote execution or image upload."""
import math
import os
import re
import json
from pathlib import Path
import numpy as np
from PIL import Image
os.environ.setdefault('USE_TF','0')
import torch
from transformers import TrOCRProcessor,NougatProcessor,VisionEncoderDecoderModel
from .common import MODELS

class TransformerOCR:
    def __init__(self,device='cuda'):
        self.device=device;self.loaded={}
    def load(self,script):
        if script not in self.loaded:
            path=MODELS/({'arabic':'nougat_arabic','latin':'trocr_latin','date':'trocr_dates','numeric':'trocr_numbers'}[script])
            if not (path/'model.safetensors').exists():raise FileNotFoundError(f'OCR checkpoint not downloaded: {path}')
            processor=(NougatProcessor if script=='arabic' else TrOCRProcessor).from_pretrained(path,local_files_only=True)
            model=VisionEncoderDecoderModel.from_pretrained(path,local_files_only=True,use_safetensors=True).to(self.device).eval()
            if self.device=='cuda':model.half()
            self.loaded[script]=(processor,model)
        return self.loaded[script]
    @torch.inference_mode()
    def read(self,image,script,debug_dir=None):
        processor,model=self.load(script)
        values=processor(images=image.convert('RGB'),return_tensors='pt').pixel_values.to(self.device,dtype=next(model.parameters()).dtype)
        output=model.generate(values,max_new_tokens=64,num_beams=1,do_sample=False,use_cache=True,return_dict_in_generate=True,output_scores=True)
        text=processor.batch_decode(output.sequences,skip_special_tokens=True)[0].strip()
        # Field crops are not Markdown documents: retain decoder output verbatim
        # rather than applying Nougat's document-rewriting postprocessor.
        # Greedy transition scores without relying on a top-level vocab_size, which
        # older VisionEncoderDecoderConfig versions do not expose.
        tokens=output.sequences[0,-len(output.scores):]
        scores=torch.stack([logits[0].float().log_softmax(-1)[token] for logits,token in zip(output.scores,tokens)])
        score=float(torch.exp(scores.float().mean()).item()) if len(scores) else 0.
        warnings=output_warnings(text,len(scores))
        result=dict(text=text,token_confidence=min(.3 if warnings else 1.,score),model={'arabic':'nougat_arabic','latin':'trocr_latin','date':'trocr_dates','numeric':'trocr_numbers'}[script],token_count=len(scores),warnings=warnings)
        if debug_dir is not None:
            folder=Path(debug_dir);folder.mkdir(parents=True,exist_ok=True)
            image.save(folder/'crop_before_processor.png')
            actual=values.detach().cpu();torch.save(actual,folder/'exact_pixel_values.pt')
            config=processor.image_processor
            mean=torch.tensor(config.image_mean).view(3,1,1);std=torch.tensor(config.image_std).view(3,1,1)
            restored=(actual[0].float()*std+mean).clamp(0,1)
            Image.fromarray((restored.permute(1,2,0).numpy()*255).round().astype(np.uint8)).save(folder/'model_input.png')
            result['debug']=dict(directory=str(folder),input_shape=list(values.shape),input_dtype=str(values.dtype),raw_decoded=processor.batch_decode(output.sequences,skip_special_tokens=False)[0],token_ids=output.sequences[0].tolist(),visualization_note='PNG is a rounded visualization of the actual normalized tensor; exact_pixel_values.pt preserves exact model input.')
            (folder/'ocr_output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        return result

def output_warnings(text,token_count):
    warnings=[]
    if token_count>=64:warnings.append('OCR_GENERATION_LIMIT')
    if not any(c.isalnum() for c in text):warnings.append('OCR_NO_ALPHANUMERIC_CONTENT')
    if re.search(r'(\S{2,})\s*(?:\1\s*){3,}',text):warnings.append('OCR_REPETITION')
    if '##' in text or '[MISSING_PAGE' in text or '![' in text or '***' in text:warnings.append('OCR_GENERATION_ARTIFACT')
    return warnings
