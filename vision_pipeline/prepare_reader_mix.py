"""Mix synthetic field crops with broad vocabulary, without reading organizer data."""
import argparse
import hashlib
import json
import os
import random
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
os.environ.setdefault('USE_TF','0')
from transformers import AutoTokenizer
from .common import ROOT,MODELS
from .date_ocr.generate import render,LATIN,ARABIC


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--fields',type=Path,default=ROOT/'data/processed/latin_ocr_tight_v3')
    ap.add_argument('--train',type=int,default=10000);ap.add_argument('--val',type=int,default=1000);ap.add_argument('--test',type=int,default=1000)
    ap.add_argument('--script',choices=['latin','arabic'],default='latin')
    ap.add_argument('--extra-train-fonts',nargs='*',default=[])
    args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Choose a new dataset directory')
    held_out=set((ARABIC if args.script=='arabic' else LATIN)[-2:])
    if held_out.intersection(args.extra_train_fonts):raise ValueError('Never train on held-out font families')
    for family in args.extra_train_fonts:
        if not family.isalpha() or not list((ROOT/'data/handwriting_fonts'/family).glob('*.ttf')):raise ValueError('Missing font: '+family)
    tokenizer=AutoTokenizer.from_pretrained(MODELS/('trocr_arabic' if args.script=='arabic' else 'trocr_latin'),local_files_only=True)
    training_tokenizer=AutoTokenizer.from_pretrained(MODELS/'trocr_latin',local_files_only=True)
    vocabulary=set()
    for token,index in tokenizer.get_vocab().items():
        if args.script=='latin' and not token.startswith('Ġ'):continue
        if args.script=='arabic' and token.startswith('##'):continue
        word=tokenizer.decode([index]).strip()
        if 3<=len(word)<=16 and word.isalpha() and all(args.script.upper() in unicodedata.name(c,'') for c in word):vocabulary.add(word)
    pools={split:[] for split in ['train','val','test']}
    for word in sorted(vocabulary):
        bucket=int(hashlib.sha256(word.casefold().encode()).hexdigest()[:8],16)%10
        pools['val' if bucket==8 else 'test' if bucket==9 else 'train'].append(word)
    rows=[];args.output.mkdir(parents=True)
    for line in (args.fields/'labels.jsonl').read_text().splitlines():
        row=json.loads(line);row['image']=str((args.fields/row['image']).resolve());rows.append(row)
    generated=[]
    for split,count in [('train',args.train),('val',args.val),('test',args.test)]:
        families=ARABIC if args.script=='arabic' else LATIN
        fonts=families[:-2] if split=='train' else [families[-2] if split=='val' else families[-1]]
        if split=='train':fonts=fonts+args.extra_train_fonts
        (args.output/split).mkdir()
        for index in range(count):
            seed=int.from_bytes(hashlib.sha256(f'reader-mix-v1:{split}:{index}'.encode()).digest()[:8],'big');rng=random.Random(seed)
            kind=rng.choices(['words','name','sentence','acronym','alphanumeric'],[4,2,2,1,1])[0]
            words=rng.sample(pools[split],rng.randint(1,3) if kind!='sentence' else rng.randint(3,6))
            text=' '.join(words)
            if kind=='name':text=' '.join(word.title() for word in words)
            elif kind=='sentence':text=text.capitalize()+rng.choice(['.',';',':',''])
            elif kind=='acronym':text=''.join(rng.choices('ابتثجحخدذرزسشصضطظعغفقكلمنهوي' if args.script=='arabic' else 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',k=rng.randint(2,6)))
            elif kind=='alphanumeric':text=''.join(rng.choices('ابتثجحخدذرزسشصضطظعغفقكلمنهوي٠١٢٣٤٥٦٧٨٩' if args.script=='arabic' else 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',k=rng.randint(3,10)))
            elif rng.random()<.2:text=text.upper()
            while len(training_tokenizer(text,add_special_tokens=False).input_ids)>63:
                text=' '.join(text.split()[:-1])
                if not text:raise ValueError('Single-word label exceeds decoder limit')
            generated.append(dict(image=f'{split}/{index:06d}.png',text=text,split=split,language=args.script,format='open_vocabulary_'+kind,font=rng.choice(fonts),seed=seed))
    def save(row):
        image,augmentation=render(row['text'],row['font'],random.Random(row['seed']))
        image.save(args.output/row['image']);return dict(row,augmentation=augmentation)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for index,row in enumerate(pool.map(save,generated),1):
            rows.append(row)
            if index%1000==0:print(index,'general crops',flush=True)
    (args.output/'labels.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    (args.output/'dataset.json').write_text(json.dumps(dict(vocabulary_source='Whole-word tokens decoded from existing pretrained tokenizer; no organizer text',
        vocabulary_sizes={k:len(v) for k,v in pools.items()},general_samples=len(generated),total_samples=len(rows),extra_train_fonts=args.extra_train_fonts,
        splits='General word pools disjoint by casefolded SHA-256; handwriting fonts disjoint. Field crops retain original splits.'),indent=2))
    print(args.output,flush=True)


if __name__=='__main__':main()
