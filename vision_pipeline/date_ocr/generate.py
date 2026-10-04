"""Reproducible labeled date crops; no organizer images or handwriting used."""
import argparse,csv,hashlib,html,io,json,random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
from .common import *

LATIN=['allura','dancingscript','caveat','marckscript','badscript','sacramento','kalam','patrickhand','handlee','shadowsintolight','satisfy','parisienne']
ARABIC=['amiri','arefruqaa','lateef','scheherazadenew','reemkufi','mirza']
MONTHS={
 'en':'January February March April May June July August September October November December'.split(),
 'fr':'janvier février mars avril mai juin juillet août septembre octobre novembre décembre'.split(),
 'ar':'يناير فبراير مارس أبريل مايو يونيو يوليو أغسطس سبتمبر أكتوبر نوفمبر ديسمبر'.split()}

def format_date(d,rng,lang):
    draw=rng.random();order='DMY';kind='numeric'
    if draw<.63:
        order=rng.choices(['DMY','MDY','YMD'],[.75,.15,.10])[0]
        sep=rng.choices(['/','-','.'],[.8,.12,.08])[0]
        year=str(d.year) if rng.random()>.10 else f'{d.year%100:02d}'
        dd=f'{d.day:02d}' if rng.random()<.9 else str(d.day)
        mm=f'{d.month:02d}' if rng.random()<.9 else str(d.month)
        parts={'D':dd,'M':mm,'Y':year};text=sep.join(parts[x] for x in order)
        if len(year)==2:kind='two_digit_year'
    else:
        month=MONTHS[lang][d.month-1];day=str(d.day);kind='written_month'
        if lang=='en' and rng.random()<.5:
            suffix='th' if 10<=d.day%100<=20 else {1:'st',2:'nd',3:'rd'}.get(d.day%10,'th');day+=suffix
        if lang=='fr' and d.day==1 and rng.random()<.5:day='1er'
        text=f'{day} {month} {d.year}'
        if draw>.94:text=f'{day} {month}';kind='missing_year'
        elif lang=='en' and rng.random()<.25:text=f'{month} {day}, {d.year}';order='MDY'
    if lang=='ar':text=text.translate(str.maketrans('0123456789','٠١٢٣٤٥٦٧٨٩'))
    return text,kind,order

def render(text,family,rng):
    paths=sorted((ROOT/'data/handwriting_fonts'/family).glob('*.ttf'))
    path=next((p for p in paths if 'Regular' in p.name),paths[0])
    font=ImageFont.truetype(str(path),rng.randint(37,68))
    direction='rtl' if any('\u0620'<=c<='\u064a' for c in text) else 'ltr'
    box=font.getbbox(text or '12/12/2026',direction=direction)
    w,h=box[2]-box[0],box[3]-box[1]
    mask=Image.new('L',(w+24,h+22));draw=ImageDraw.Draw(mask)
    if text:draw.text((12-box[0],10-box[1]),text,font=font,fill=255,direction=direction,stroke_width=1 if rng.random()<.1 else 0)
    # Vary slant, character height, stroke width and baseline without changing text.
    shear=rng.uniform(-.14,.18);array=np.asarray(mask)
    matrix=np.float32([[1,shear,abs(shear)*mask.height],[0,1,0]])
    array=cv2.warpAffine(array,matrix,(mask.width+int(abs(shear)*mask.height*2)+1,mask.height))
    if rng.random()<.13:array=cv2.dilate(array,np.ones((2,2),np.uint8))
    mask=Image.fromarray(array)
    mask=mask.resize((max(20,round(mask.width*rng.uniform(.83,1.18))),max(15,round(mask.height*rng.uniform(.85,1.2)))))
    bg=rng.choice([(246,191,207)]*5+[(255,255,250),(235,228,215),(244,244,244)])
    color=rng.choice([(20,38,125),(24,65,160),(15,20,29),(38,40,65)])
    image=Image.new('RGB',mask.size,bg);image.paste(color,(0,0),mask)
    underline=rng.random()<.65
    if underline:
        draw=ImageDraw.Draw(image);y=image.height-rng.randint(1,8)
        draw.line((0,y,image.width,y+rng.choice([-1,0,1])),fill=rng.choice([(65,55,60),(85,80,80)]),width=rng.choice([1,1,2]))
    angle=rng.uniform(-4,4)
    image=image.rotate(angle,Image.Resampling.BICUBIC,expand=True,fillcolor=bg)
    # Match small detector crops instead of providing only unrealistically sharp text.
    target_h=rng.randint(23,56);ratio=target_h/image.height
    image=image.resize((max(30,round(image.width*ratio)),target_h),Image.Resampling.LANCZOS)
    profile=rng.choices(['clean','blur','low_resolution','shadow','noisy'],[.42,.14,.16,.12,.16])[0]
    if profile=='blur':image=image.filter(ImageFilter.GaussianBlur(rng.uniform(.25,.65)))
    if profile=='low_resolution':
        factor=rng.uniform(.58,.83);image=image.resize((max(15,int(image.width*factor)),max(12,int(image.height*factor))),Image.Resampling.BILINEAR).resize(image.size,Image.Resampling.BILINEAR)
    arr=np.asarray(image).astype(np.float32);nrng=np.random.default_rng(rng.randrange(2**32))
    if profile=='shadow':arr*=np.linspace(rng.uniform(.55,.8),1,image.width)[None,:,None]
    if profile=='noisy':arr+=nrng.normal(0,rng.uniform(2,6),arr.shape)
    image=Image.fromarray(arr.clip(0,255).astype(np.uint8))
    buffer=io.BytesIO();quality=rng.randint(35,68) if profile!='clean' else rng.randint(85,97)
    image.save(buffer,format='JPEG',quality=quality);image=Image.open(io.BytesIO(buffer.getvalue())).convert('RGB')
    return image,dict(profile=profile,rotation=round(angle,3),underline=underline,jpeg_quality=quality)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--train',type=int,default=6000);ap.add_argument('--val',type=int,default=600);ap.add_argument('--test',type=int,default=600);a=ap.parse_args()
    if DATASET.exists():raise SystemExit(f'Refusing to overwrite {DATASET}')
    DATASET.mkdir();rng=random.Random(2026100402)
    dates=[date(1950,1,1)+timedelta(days=i) for i in range((date(2051,1,1)-date(1950,1,1)).days)]
    rng.shuffle(dates);rows=[];offset=0
    for split,n in [('train',a.train),('val',a.val),('test',a.test)]:
        for i,d in enumerate(dates[offset:offset+n]):
            seed=2026100402+offset+i;r=random.Random(seed);lang=r.choices(['en','fr','ar'],[.4,.4,.2])[0]
            families=ARABIC if lang=='ar' else LATIN
            families=[f for f in families if f not in ['satisfy','parisienne','reemkufi','mirza']] if split=='train' else [f for f in families if f in (['satisfy','reemkufi'] if split=='val' else ['parisienne','mirza'])]
            family=r.choice(families);text,kind,order=format_date(d,r,lang)
            blank=r.random()<.03
            if blank:text='';kind='blank'
            rows.append(dict(image=f'{split}/date_{i:06d}.png',split=split,text=text,language=lang,font=family,format=kind,date_order=order,source_date=d.isoformat(),seed=seed))
        offset+=n;(DATASET/split).mkdir()
    def save(row):
        im,aug=render(row['text'],row['font'],random.Random(row['seed']+42));path=DATASET/row['image'];im.save(path)
        return dict(row,**aug,image_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    with ThreadPoolExecutor(6) as pool:
        rows=list(pool.map(save,rows))
    with (DATASET/'labels.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (DATASET/'labels.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    summary=dict(samples=len(rows),splits=dict(Counter(r['split'] for r in rows)),formats=dict(Counter(r['format'] for r in rows)),languages=dict(Counter(r['language'] for r in rows)),fonts=dict(Counter(r['font'] for r in rows)),profiles=dict(Counter(r['profile'] for r in rows)),date_range=['1950-01-01','2050-12-31'],organizer_data_used=False,split_policy='Disjoint font families and disjoint underlying dates across train/val/test.',label_policy='Exact visible transcription; missing year stays missing; numeric date order/century are not inferred by OCR.',limitations=['Font-based handwriting is not independent real writers.','Some numeric date orders and two-digit years are intrinsically ambiguous.','Arabic font rendering includes calligraphic/print-like styles, not only handwriting.'],label_sha256=hashlib.sha256((DATASET/'labels.jsonl').read_bytes()).hexdigest())
    write_json(DATASET/'report.json',summary);write_json(LOGS/'dataset.json',summary)
    chosen=[]
    for split in ['train','val','test']:
        chosen.extend([r for r in rows if r['split']==split][:48])
    cards=''.join(f'<figure><img src="{r["image"]}"><figcaption dir="auto">{html.escape(r["text"] or "[blank]")}</figcaption><small>{r["split"]} / {r["font"]} / {r["profile"]}</small></figure>' for r in chosen)
    (DATASET/'preview.html').write_text('<meta charset="utf-8"><title>Date training crops</title><style>body{font:16px system-ui;background:#eee}main{display:flex;flex-wrap:wrap}figure{background:white;padding:15px;margin:8px;width:360px}img{max-width:350px;height:65px;object-fit:contain}</style><h1>Independent synthetic date crops</h1><p>Exact transcription labels. Organizer images are not used.</p><main>'+cards+'</main>')
    sheet=Image.new('RGB',(1000,10*110),'white');draw=ImageDraw.Draw(sheet)
    for i,r in enumerate(chosen[:20]):
        x=(i%2)*500;y=(i//2)*110;im=Image.open(DATASET/r['image']);im.thumbnail((465,65));sheet.paste(im,(x+10,y+5));draw.text((x+10,y+75),r['font']+' / '+r['format'],fill='black')
    sheet.save(DATASET/'contact_sheet.jpg');print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
