"""Exact glyph-checked labels for numbers, units and characters; no organizer data."""
import argparse,csv,hashlib,html,json,random,string,unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from fontTools.ttLib import TTFont
from PIL import Image,ImageDraw
from ..date_ocr.generate import render,LATIN,ARABIC
from .common import *

KINDS=['temperature','mass','length','age','pressure','decimal','integer','alphanumeric','character','blank']
WEIGHTS=[20,16,14,10,7,12,7,8,5,1]

def sample(rng,lang):
    kind=rng.choices(KINDS,WEIGHTS)[0];gap=rng.choice([' ',' ','','  ']);unit='';number=''
    if kind=='temperature':
        value=rng.randint(180,550);number=f'{value/10:.1f}';unit=rng.choices(['°C','C','° C','درجة'],[.76,.07,.09,.08] if lang=='ar' else [.84,.07,.09,0])[0]
    elif kind=='mass':
        unit=rng.choice(['g','g','kg','غ','كغ'] if lang=='ar' else ['g','g','g','kg']);number=str(rng.randint(200,12000)) if unit in ['g','غ'] else f'{rng.randint(200,180000)/1000:.3f}'
    elif kind=='length':
        unit=rng.choice(['cm','cm','mm','سم'] if lang=='ar' else ['cm','cm','cm','mm']);number=str(rng.randint(15,210)) if rng.random()<.6 else f'{rng.randint(150,2100)/10:.1f}'
    elif kind=='age':
        unit=rng.choice({'en':['days','day','weeks','years'],'fr':['jours','j','sem.','ans'],'ar':['يوم','أيام','أسبوع','سنة']}[lang]);number=str(rng.randint(0,150))
    elif kind=='pressure':
        number=f'{rng.randint(60,220)}/{rng.randint(30,140)}';unit=rng.choice(['mmHg','mm Hg',''])
    elif kind=='decimal':
        digits=rng.choice([1,1,2,3]);number=f'{rng.randint(0,99999)/(10**digits):.{digits}f}'
        if rng.random()<.2:number=rng.choice(['+','-'])+number
        unit=rng.choice(['','%','g/dL','g/L','mg/dL','mmol/L','bpm','µL','mL'])
    elif kind=='integer':
        number=str(rng.randint(0,99999));unit=rng.choice(['','', 'bpm','UI','mg','mL'])
    elif kind=='alphanumeric':
        number=''.join(rng.choice(string.ascii_letters+string.digits) for _ in range(rng.randint(2,8)))
        if rng.random()<.4:number=rng.choice(['O0','0O','l1','1l','S5','5S','B8','8B','Z2','2Z','g9','9g'])+str(rng.randint(0,999))
    elif kind=='character':number=rng.choice(string.ascii_letters+string.digits+'°%+-/=.,µ±')
    elif kind=='blank':return '',kind,'blank',''
    # Split all typography/decimal/script variants of a literal value together.
    key=kind+':'+number+':'+unit
    if kind not in ['alphanumeric','character'] and '.' in number:
        if lang=='fr' and rng.random()<.55:number=number.replace('.',',')
        if lang=='ar' and rng.random()<.65:number=number.replace('.','٫')
    text=number+(gap+unit if unit else '')
    if lang=='ar' and kind not in ['alphanumeric','character']:
        text=text.translate(str.maketrans('0123456789','٠١٢٣٤٥٦٧٨٩'))
    return text,kind,key,unit

def split_for(key):
    n=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%100
    return 'train' if n<80 else 'val' if n<90 else 'test'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--train',type=int,default=9000);ap.add_argument('--val',type=int,default=900);ap.add_argument('--test',type=int,default=900);a=ap.parse_args()
    if DATASET.exists():raise SystemExit(f'Refusing to overwrite {DATASET}')
    DATASET.mkdir();cmaps={}
    for family in LATIN+ARABIC:
        paths=sorted((ROOT/'data/handwriting_fonts'/family).glob('*.ttf'));path=next((p for p in paths if 'Regular' in p.name),paths[0]);cmaps[family]=TTFont(path).getBestCmap()
    rows=[];offset=0;rejected=0
    for split,n in [('train',a.train),('val',a.val),('test',a.test)]:
        (DATASET/split).mkdir();rng=random.Random(2026100410+offset)
        for i in range(n):
            lang=rng.choices(['en','fr','ar'],[.4,.4,.2])[0]
            candidates=ARABIC if lang=='ar' else LATIN
            candidates=[f for f in candidates if f not in ['satisfy','parisienne','reemkufi','mirza']] if split=='train' else [f for f in candidates if f in (['satisfy','reemkufi'] if split=='val' else ['parisienne','mirza'])]
            family=rng.choice(candidates)
            while True:
                text,kind,key,unit=sample(rng,lang)
                if kind!='blank' and split_for(key)!=split:continue
                if not all(c.isspace() or ord(c) in cmaps[family] for c in text):rejected+=1;continue
                break
            rows.append(dict(image=f'{split}/number_{i:06d}.png',split=split,text=text,language=lang,font=family,format=kind,unit=unit,group_key=key if kind!='blank' else 'blank:'+split,seed=rng.randrange(2**32)))
        offset+=n
    def save(row):
        im,aug=render(row['text'],row['font'],random.Random(row['seed']));path=DATASET/row['image'];im.save(path)
        return dict(row,**aug,image_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    with ThreadPoolExecutor(6) as pool:rows=list(pool.map(save,rows))
    with (DATASET/'labels.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (DATASET/'labels.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    summary=dict(samples=len(rows),splits=dict(Counter(r['split'] for r in rows)),formats=dict(Counter(r['format'] for r in rows)),languages=dict(Counter(r['language'] for r in rows)),fonts=dict(Counter(r['font'] for r in rows)),profiles=dict(Counter(r['profile'] for r in rows)),degree_symbol_samples=sum('°' in r['text'] for r in rows),glyph_coverage_checked=True,unsupported_glyph_candidates_rejected=rejected,organizer_data_used=False,split_policy='Disjoint font families and value/unit grouping keys. Blank controls grouped by split.',label_policy='Exact visible transcription; no stripping units, punctuation, signs or decimal separators.',label_sha256=hashlib.sha256((DATASET/'labels.jsonl').read_bytes()).hexdigest(),limitations=['Font-based handwriting, not independent real writers.','Broad numeric examples are OCR training, not clinical guidance.','Character/alphanumeric samples do not establish general prose recognition quality.'])
    write_json(DATASET/'report.json',summary);write_json(LOGS/'dataset.json',summary)
    chosen=[]
    for split in ['train','val','test']:
        for kind in KINDS:chosen.extend([r for r in rows if r['split']==split and r['format']==kind][:4])
    cards=''.join(f'<figure><img src="{r["image"]}"><figcaption dir="auto">{html.escape(r["text"] or "[blank]")}</figcaption><small>{r["split"]} / {r["font"]} / {r["format"]}</small></figure>' for r in chosen)
    (DATASET/'preview.html').write_text('<meta charset="utf-8"><title>Numbers, units and characters</title><style>body{font:17px system-ui;background:#eee}main{display:flex;flex-wrap:wrap}figure{background:white;padding:12px;width:310px}img{max-width:300px;height:65px;object-fit:contain}</style><h1>Numbers, decimals, units and character crops</h1><p>Exact labels; glyph coverage checked; no organizer images used.</p><main>'+cards+'</main>')
    sheet=Image.new('RGB',(1050,1100),'white');draw=ImageDraw.Draw(sheet)
    for i,r in enumerate([chosen[j*4+k] for j in range(10) for k in range(3)]):
        x=i%3*350;y=i//3*110;im=Image.open(DATASET/r['image']);im.thumbnail((330,65));sheet.paste(im,(x+8,y+5));draw.text((x+8,y+78),r['font']+' / '+r['format'],fill='black')
    sheet.save(DATASET/'contact_sheet.jpg');print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
