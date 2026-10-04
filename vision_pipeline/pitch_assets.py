"""Reproduce real dataset evidence from the existing renderer, not invented artwork."""
import hashlib,json,sys
from PIL import Image
import fitz
from .common import ROOT,BASE,read_json,write_json

def prepare():
    sys.path.insert(0,str(ROOT/'scripts'))
    from generate_diverse_forms import blank_template,render,W,H,PDF
    folder=BASE/'presentation/assets';folder.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(PDF.read_bytes()).hexdigest();doc=fitz.open(PDF);page=doc[5]
    pix=page.get_pixmap(matrix=fitz.Matrix(W/page.rect.width,H/page.rect.height),alpha=False)
    original=Image.frombytes('RGB',(pix.width,pix.height),pix.samples).resize((W,H))
    blank=blank_template(doc,6)
    source=ROOT/'data/forms/06_early_postnatal_newborn'
    record=next(json.loads(s) for s in (source/'annotations.jsonl').read_text().splitlines() if json.loads(s)['image_filename']=='06_000004.jpg')
    clean,fields,*_=render(blank,read_json(source/'field_layout.json'),6,4,record['random_seed'])
    assert all(f['rendered_text']==record['fields'][k]['rendered_text'] for k,f in fields.items())
    augmented=Image.open(source/'images'/record['image_filename']).convert('RGB')
    for name,im in [('source',original),('blank',blank),('synthetic',clean),('augmented',augmented)]:
        im.save(folder/(name+'.png'))
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==digest
    write_json(folder/'provenance.json',dict(source_pdf=str(PDF.relative_to(ROOT)),source_sha256=digest,page=6,synthetic_record=record['image_filename'],seed=record['random_seed'],font=record['font_family'],language=record['language'],augmentation=record['distortions'],renderer_replay_verified=True,source_unchanged=True,method='Read supplied vector PDF in memory. Remove /F3 handwriting text objects and blue vector mark paths; retain printed artwork. Render exact labels with the existing handwriting-font renderer. Augmented image is the actual saved dataset page. This is not general raster handwriting erasure or generative handwriting.'))
    return folder

if __name__=='__main__':print(prepare())
