"""Expose actual selected-option examples, not merely field-presence counts."""
import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path
from PIL import Image,ImageDraw
from schema_form_layout import schema_leaves

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);root=ap.parse_args().root
    previews=root/'option_examples';previews.mkdir(exist_ok=True)
    parts=['<meta charset="utf-8"><title>Every option: actual image examples</title><style>body{font:16px sans-serif;margin:24px}section{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}article{border:1px solid #ccc;padding:12px}img{width:100%}h2{margin-top:40px}</style>',
           '<h1>Selected-option coverage — corrected v3 dataset</h1><p>Each card links to a full generated image with this option selected. Counts include KNOWN labels only. False booleans show unchecked boxes; array values count actual selected options. Preprinted identifiers are identified separately.</p>']
    rows=[];first_form_cards=[]
    ranks={v:i for i,v in enumerate(['clean','shadow','perspective','rotated','low_quality','heavy'])}
    for folder in sorted(root.glob('[0-9][0-9]_*')):
        specs=schema_leaves(int(folder.name[:2]));counts=Counter();best={}
        for line in (folder/'annotations.jsonl').open():
            r=json.loads(line)
            for key,f in r['fields'].items():
                sk=f['schema_path'];spec=specs[sk]
                if spec['type'] not in ['enum','boolean','array'] or f['status']!='KNOWN':continue
                values=f['canonical_value'] if isinstance(f['canonical_value'],list) else [f['canonical_value']]
                for value in values:
                    counts[sk,str(value),r['language']]+=1;k=(sk,str(value))
                    rank=(ranks[r['profile']],r['language']!='fr',r['image_filename'])
                    if k not in best or rank<best[k][0]:best[k]=(rank,r,f,value)
        parts.append(f'<h2 id="{folder.name}">{folder.name}</h2><section>')
        for sk,spec in specs.items():
            expected=spec.get('values',spec.get('items',{}).get('values',[True,False] if spec['type']=='boolean' else []))
            for value in expected:
                k=(sk,str(value));assert k in best,(folder.name,k)
                _,r,f,_=best[k];full=folder/'images'/r['image_filename'];b=f['bbox']
                for comp in f.get('components',[]):
                    if comp['value']==value or isinstance(comp['value'],list) and value in comp['value']:b=comp['bbox'];break
                cropfile=previews/f'{len(rows):04d}.jpg'
                with Image.open(full) as im:
                    w,h=im.size;crop=im.crop((max(0,int((b[0]-.11)*w)),max(0,int((b[1]-.018)*h)),min(w,int((b[2]+.25)*w)),min(h,int((b[3]+.025)*h))))
                    crop.thumbnail((800,260));crop.save(cropfile,quality=92)
                row=dict(form=folder.name,schema_path=sk,option=str(value),en_count=counts[sk,str(value),'en'],fr_count=counts[sk,str(value),'fr'],ar_count=counts[sk,str(value),'ar'],example_image=str(full.relative_to(root)),kind=f['kind'])
                assert min(row['en_count'],row['fr_count'],row['ar_count'])>0,row
                rows.append(row);title=html.escape(f'{sk} = {value}')
                parts.append(f'<article><strong>{title}</strong><p>EN {row["en_count"]} · FR {row["fr_count"]} · AR {row["ar_count"]} · {f["kind"]}</p><a href="{row["example_image"]}"><img src="{cropfile.relative_to(root)}"><br>Open full image</a></article>')
                if folder.name.startswith('01_'):first_form_cards.append((f'{sk}: {value}',cropfile))
        parts.append('</section>')
    (root/'option_coverage.html').write_text('\n'.join(parts))
    with (root/'option_coverage.csv').open('w',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    sheet=Image.new('RGB',(1440,200*((len(first_form_cards)+2)//3)),'white');draw=ImageDraw.Draw(sheet)
    for i,(title,path) in enumerate(first_form_cards):
        x=i%3*480;y=i//3*200;draw.text((x+8,y+8),title,fill='black')
        with Image.open(path) as im:
            im.thumbnail((460,155));sheet.paste(im,(x+8,y+32))
    sheet.save(root/'monitoring_all_options.jpg',quality=94)
    print(f'{len(rows)} option cards, each present in EN/FR/AR; {len(first_form_cards)} monitoring-form options.')

if __name__=='__main__':main()
