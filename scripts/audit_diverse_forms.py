"""Decode all images, check label correspondence and boxes, export flat field CSVs."""
import argparse
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
from PIL import Image,ImageDraw
from schema_form_layout import schema_leaves
from schema_form_values import nested_labels

csv.field_size_limit(10_000_000)

def valid_value(value,spec):
    if value is None:return True
    typ=spec['type']
    if typ=='boolean':return isinstance(value,bool)
    if typ in ['integer','double']:return isinstance(value,(int,float)) and not isinstance(value,bool)
    if typ=='enum':return value in spec['values']
    if typ=='array':return isinstance(value,list) and all(v in spec['items']['values'] for v in value)
    if typ=='date':
        from datetime import date
        try:date.fromisoformat(value);return True
        except (ValueError,TypeError):return False
    return isinstance(value,str)

def audit(root):
    root=Path(root)
    errors=[];pages=fields_total=0;fonts=defaultdict(set);counts=Counter();examples={};splits=defaultdict(list);schema_report=[];instance_report=[]
    for form in sorted(root.glob('[0-9][0-9]_*')):
        specs=schema_leaves(int(form.name[:2]));schema_counts=Counter();marked=Counter();options=defaultdict(set);kinds={};instances=Counter();instance_marks=Counter();instance_kinds={}
        rows=list(csv.DictReader((form/'labels.csv').open()))
        byname={r['image_filename']:r for r in rows};seen=set();coverage=Counter()
        with (form/'field_labels.csv').open('w',newline='') as out:
            columns=['image_filename','field','schema_path','canonical_value','rendered_text','status','kind','bbox','language','font_family','split']
            writer=csv.DictWriter(out,fieldnames=columns);writer.writeheader()
            for line in (form/'annotations.jsonl').open():
                record=json.loads(line);name=record['image_filename'];path=form/'images'/name
                if name in seen:errors.append(f'duplicate label {path}')
                seen.add(name);row=byname.get(name)
                if row is None or json.loads(row['fields_json'])!=record['fields']:errors.append(f'CSV mismatch {path}')
                if json.loads(row['schema_json'])!=record['schema'] or record['schema']!=nested_labels(record['fields']):errors.append(f'schema envelope mismatch {path}')
                with Image.open(path) as image:
                    image.load()
                    if image.size!=(1654,2339):errors.append(f'wrong dimensions {path}')
                for key,f in record['fields'].items():
                    sk=f['schema_path'];lang=record['language'];kinds[sk]=f['kind']
                    instance_kinds[key]=f['kind'];instances[key,lang]+=f['status']=='KNOWN';instance_marks[key,lang]+=f['visible_mark']
                    if sk not in specs or not valid_value(f['canonical_value'],specs[sk]):errors.append(f'invalid schema value {path} {key}')
                    if f['status']=='KNOWN':
                        schema_counts[sk,lang]+=1;marked[sk,lang]+=f['visible_mark']
                        val=f['canonical_value']
                        if specs[sk]['type'] in ['enum','boolean','array']:
                            options[sk,lang].update(val if isinstance(val,list) else [val])
                    b=f['bbox']
                    if not (0<=b[0]<b[2]<=1 and 0<=b[1]<b[3]<=1):errors.append(f'bad box {path} {key}')
                    for component in f.get('components',[]):
                        cb=component['bbox']
                        if not (0<=cb[0]<cb[2]<=1 and 0<=cb[1]<cb[3]<=1):errors.append(f'bad option box {path} {key}')
                    coverage[key]+=f['status']=='KNOWN';fields_total+=1
                    writer.writerow(dict(image_filename=name,field=key,schema_path=sk,canonical_value=json.dumps(f['canonical_value'],ensure_ascii=False),
                        rendered_text=f['rendered_text'],status=f['status'],kind=f['kind'],bbox=json.dumps(b),
                        language=record['language'],font_family=record['font_family'],split=record['split']))
                pages+=1;fonts[record['font_family']].add(record['split']);counts[record['profile']]+=1
                splits[record['split']].append(str(path.relative_to(root)))
                examples.setdefault((form.name,record['language'],record['profile']),path)
        if len(rows)!=len(seen) or len(list((form/'images').glob('*.jpg')))!=len(seen):errors.append(f'count mismatch {form}')
        if any(n==0 for n in coverage.values()):errors.append(f'never filled field {form}')
        for key,spec in specs.items():
            for lang in ['en','fr','ar']:
                count=schema_counts[key,lang];visible=marked[key,lang]
                if count==0 or (visible==0 and kinds.get(key)!='printed'):errors.append(f'unfilled schema field {form.name}/{key}/{lang}')
                expected=spec.get('values',spec.get('items',{}).get('values',[True,False] if spec['type']=='boolean' else []))
                missing=set(expected)-options[key,lang]
                if missing:errors.append(f'missing option {form.name}/{key}/{lang}: {missing}')
                schema_report.append(dict(form=form.name,schema_path=key,language=lang,known_instances=count,visible_filled_instances=visible,kind=kinds.get(key),missing_options=json.dumps(list(missing))))
        for key,kind in instance_kinds.items():
            for lang in ['en','fr','ar']:
                count=instances[key,lang];visible=instance_marks[key,lang]
                if not count or (not visible and kind!='printed'):errors.append(f'unfilled indexed field {form.name}/{key}/{lang}')
                instance_report.append(dict(form=form.name,field=key,language=lang,known_instances=count,visible_filled_instances=visible,kind=kind))
        print(f'{form.name}: {len(seen)} pages; {len(coverage)} mapped fields; minimum fill count {min(coverage.values())}',flush=True)
    for family,ss in fonts.items():
        if len(ss)!=1:errors.append(f'font leakage {family}')
    for split,paths in splits.items():(root/f'{split}.txt').write_text('\n'.join(paths)+'\n')
    previews=root/'contact_sheets';previews.mkdir(exist_ok=True)
    for form in sorted(root.glob('[0-9][0-9]_*')):
        for lang in ['en','fr','ar']:
            sheet=Image.new('RGB',(1200,1140),'white');draw=ImageDraw.Draw(sheet)
            for i,profile in enumerate(['clean','rotated','low_quality','shadow','heavy','perspective']):
                path=examples.get((form.name,lang,profile))
                if not path:errors.append(f'missing combo {form.name}/{lang}/{profile}');continue
                with Image.open(path) as image:
                    image.thumbnail((390,540));sheet.paste(image,((i%3)*400,(i//3)*570+25))
                draw.text(((i%3)*400+10,(i//3)*570+5),profile,fill='black')
            sheet.save(previews/f'{form.name}_{lang}.jpg',quality=88)
    with (root/'schema_coverage.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(schema_report[0]));writer.writeheader();writer.writerows(schema_report)
    with (root/'indexed_field_coverage.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(instance_report[0]));writer.writeheader();writer.writerows(instance_report)
    report=dict(pages=pages,field_labels=fields_total,schema_leaf_fields=len(schema_report)//3,indexed_fields=len(instance_report)//3,fully_covered_schema_language_pairs=sum(r['known_instances']>0 and (r['visible_filled_instances']>0 or r['kind']=='printed') for r in schema_report),profiles=dict(counts),splits={s:len(v) for s,v in splits.items()},
                font_families=len(fonts),errors=errors,passed=not errors)
    (root/'integrity_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path)
    audit(ap.parse_args().root)
