"""Extra full-sentence line annotations; synthetic form 06 only, no organizer ink.

Train/val/test retain the existing font-disjoint split. Original short fields are
replayed alongside new long text; a whole rendered sentence is ONE target box.
"""
import argparse,csv,hashlib,json,random,sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import fitz,yaml
from .common import *
sys.path.insert(0,str(ROOT/'scripts'))
from generate_diverse_forms import render,blank_template,distort_spec,save_camera,W,H,PDF

LONG_DATA=DATA/'long_handwriting'
LONG_LOGS=REPORTS/'long_handwriting'
LONG_WEIGHTS=MODELS/'long_handwriting'/'handwriting'/'weights'/'best.pt'
LONG_OUTPUT=BASE/'outputs'/'long_handwriting'

# Independent synthetic vocabulary, not transcripts extracted from organizer pages.
PHRASES={
 'fr':[
  'Surveillance quotidienne de la prise alimentaire et du poids',
  'Expliquer aux parents les signes qui nécessitent une consultation',
  'Revoir le nourrisson au centre de santé la semaine prochaine',
  'Conseils donnés pour le repos et la protection contre le froid',
  'Continuer les soins et noter les changements observés à domicile',
  'Organiser une visite de contrôle avec un professionnel de santé',
  'La famille a reçu les explications concernant le suivi du bébé',
  'Vérifier le carnet et compléter les informations à la prochaine visite'],
 'en':[
  'Daily monitoring of feeding and changes in body weight',
  'Explain the warning signs that require a medical consultation',
  'Review the newborn at the health centre during the next week',
  'Parents received advice about rest and protection from cold',
  'Continue care and record any changes observed at home',
  'Arrange a follow up appointment with a health professional',
  'The family received information about the next scheduled visit',
  'Check the record and complete the details at the next visit'],
 'ar':[
  'متابعة الرضاعة وقياس الوزن بصورة منتظمة في المركز الصحي',
  'شرح العلامات التي تستدعي مراجعة الطبيب في أقرب وقت',
  'إعادة فحص الطفل في المركز الصحي خلال الأسبوع القادم',
  'تقديم نصائح للأسرة حول الراحة وحماية الطفل من البرد',
  'مواصلة الرعاية وتسجيل التغيرات التي تلاحظها الأسرة في المنزل',
  'تحديد موعد جديد للمتابعة مع أحد العاملين في المركز الصحي',
  'تلقت الأسرة المعلومات الضرورية حول الزيارة المقبلة للطفل',
  'مراجعة السجل واستكمال المعلومات خلال الزيارة القادمة']}
KEYS=['decision','treatment','referral_facility','vaccination_status','examiner_role','other_danger_sign','other_trauma_or_malformation']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pages',type=int,default=720);a=ap.parse_args()
    if LONG_DATA.exists():raise SystemExit('Choose a new dataset path instead of overwriting prepared data.')
    LONG_DATA.mkdir(parents=True);LONG_LOGS.mkdir(parents=True,exist_ok=True)
    doc=fitz.open(PDF);template=blank_template(doc,6);slots=read_json(SOURCE/'field_layout.json')
    def process(index):
        seed=861730+index;rng=random.Random(seed);lang=['en','fr','ar'][index%3]
        overrides={}
        for key in KEYS:
            words=rng.choice(PHRASES[lang]).split()
            # Retain short phrases as well as 5-14-word full sentences.
            words=words[:rng.randint(3,len(words))] if rng.random()<.3 else words
            if rng.random()<.25:words+=rng.choice(PHRASES[lang]).split()[:rng.randint(2,4)]
            overrides[key]=' '.join(words)
        image,fields,_,lang,font,split=render(template,slots,6,index,seed,capture_text_boxes=True,text_overrides=overrides,text_width_fraction=rng.uniform(.55,1.))
        split={'train':'train','validation':'val','synthetic_test':'test'}[split]
        matrix,meta=distort_spec(index//3+index//36,seed)
        # CPU camera warp while CUDA is occupied by OCR; YOLO training uses CUDA.
        arr=cv2.warpPerspective(np.asarray(image),matrix,(W,H),borderValue=(255,255,255))
        if meta['blur']:arr=cv2.GaussianBlur(arr,(5,5),0)
        if meta['noise']:
            noise=np.random.default_rng(seed).normal(0,255*meta['noise'],arr.shape)
            arr=np.clip(arr.astype(np.float32)+noise,0,255).astype('uint8')
        image=Image.fromarray(arr);name=f'long_{index:06d}.jpg';dest=LONG_DATA/'images'/split/name;dest.parent.mkdir(parents=True,exist_ok=True)
        digest=save_camera(image,dest,meta);ink=[];lines=[]
        for key,f in fields.items():
            for region in f.get('text_regions',[]):
                q=cv2.perspectiveTransform((quad(region['bbox'])*[W,H]).astype(np.float32)[None],matrix)[0]/[W,H]
                assert (q>=0).all() and (q<=1).all()
                ink.append(dict(field=key,text=region['text'],quad=q.tolist(),words=len(region['text'].split()),target='complete_line'))
                lines.append('0 '+' '.join(f'{v:.8f}' for v in q.ravel()))
        label=LONG_DATA/'labels'/split/(Path(name).stem+'.txt');label.parent.mkdir(parents=True,exist_ok=True);label.write_text('\n'.join(lines)+'\n')
        if index in [0,1,2,36,37,38]:
            preview=image.copy();draw=__import__('PIL.ImageDraw',fromlist=['Draw']).Draw(preview)
            for r in ink:
                q=np.asarray(r['quad'])*[W,H];draw.line([tuple(p) for p in np.vstack([q,q[:1]])],fill='red',width=3)
            preview.thumbnail((827,1170));preview.save(LONG_LOGS/f'labels_{index:04d}.jpg')
        return dict(image=name,split=split,language=lang,font=font,profile=meta['profile'],image_sha256=digest,ink=ink)
    rows=[]
    with ThreadPoolExecutor(6) as pool:
        for i,row in enumerate(pool.map(process,range(a.pages)),1):
            rows.append(row)
            if i%60==0:print('long-line pages',i,'/',a.pages,flush=True)
    # Mix original short-field pages without copying images or changing old labels.
    original=[]
    for line in (WORK/'ink_labels.jsonl').read_text().splitlines():
        row=json.loads(line);original.append(row)
        for kind,suffix in [('images','.jpg'),('labels','.txt')]:
            source=WORK/'handwriting'/kind/row['split']/(Path(row['image']).stem+suffix)
            target=LONG_DATA/kind/row['split']/source.name;target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(source.resolve())
    (LONG_DATA/'labels.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    with (LONG_DATA/'labels.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['image','split','language','font','field','text','words','quad']);writer.writeheader()
        for r in rows:
            for ink in r['ink']:writer.writerow({k:r[k] for k in ['image','split','language','font']}|{k:ink[k] for k in ['field','text','words']}|dict(quad=json.dumps(ink['quad'])))
    (LONG_DATA/'dataset.yaml').write_text(yaml.safe_dump(dict(path=str(LONG_DATA),train='images/train',val='images/val',test='images/test',names={0:'handwriting_line'})))
    report=dict(new_pages=len(rows),original_pages=len(original),new_splits=dict(Counter(r['split'] for r in rows)),mixed_splits=dict(Counter(r['split'] for r in rows+original)),new_regions=sum(len(r['ink']) for r in rows),long_regions_5plus_words=sum(x['words']>=5 for r in rows for x in r['ink']),fonts=dict(Counter(r['font'] for r in rows)),labels_sha256=hashlib.sha256((LONG_DATA/'labels.jsonl').read_bytes()).hexdigest(),organizer_handwriting_used=False,source='Blank form-06 artwork + independent synthetic sentence vocabulary; exact renderer-alpha full-line boxes. Original short fields mixed in.',limitations=['Font synthesis, not real human writers.','Single-line sentences only; multiline grouping is not implemented.','Shared template, font-disjoint synthetic splits; vocabulary is shared across splits.','Some forced text overrides ignore clinical applicability; this dataset trains ink localization, not clinical decisions.'])
    write_json(LONG_DATA/'preparation.json',report);write_json(LONG_LOGS/'preparation.json',report);print(report,flush=True)

if __name__=='__main__':main()
