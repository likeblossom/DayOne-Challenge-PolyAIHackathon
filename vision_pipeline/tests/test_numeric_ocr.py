import json
from collections import defaultdict
from vision_pipeline.numeric_ocr.common import DATASET
from vision_pipeline.label_anchor_pilot.infer import ocr_routes

def test_record_identifier_routes_numeric_and_preserves_other_strings():
    route=dict(label='latin',confidence=.99)
    assert ocr_routes(route,'string',True,True,'record_code')==['numeric']
    assert ocr_routes(route,'string',True,True,'region')==['latin']
from vision_pipeline.label_anchor_pilot.long_lines import LONG_DATA

def test_specialists_preserve_other_routes():
    route=dict(label='latin',confidence=.99)
    assert ocr_routes(route,'double',True,True)==['numeric']
    assert ocr_routes(route,'integer',True,True)==['numeric']
    assert ocr_routes(route,'date',True,True)==['date']
    assert ocr_routes(route,'string',True,True)==['latin']
    assert ocr_routes(route,'double')==['latin','arabic']
    assert ocr_routes(dict(label='arabic',confidence=.99),'string',True,True)==['arabic']

def test_numeric_data_split_and_symbols():
    if not (DATASET/'labels.jsonl').exists():return
    rows=[json.loads(x) for x in (DATASET/'labels.jsonl').read_text().splitlines()]
    groups=defaultdict(set);fonts=defaultdict(set)
    for r in rows:groups[r['split']].add(r['group_key']);fonts[r['split']].add(r['font'])
    for a,b in [('train','val'),('train','test'),('val','test')]:
        assert not groups[a]&groups[b];assert not fonts[a]&fonts[b]
    train=[r['text'] for r in rows if r['split']=='train']
    for symbol in ['°',',','.','٠','µ','%']:
        assert any(symbol in text for text in train),symbol

def test_long_lines_have_single_complete_targets():
    if not (LONG_DATA/'labels.jsonl').exists():return
    rows=[json.loads(x) for x in (LONG_DATA/'labels.jsonl').read_text().splitlines()]
    count=0;fonts=defaultdict(set)
    for r in rows:
        fonts[r['split']].add(r['font']);keys=[]
        lines=(LONG_DATA/'labels'/r['split']/(r['image'].replace('.jpg','.txt'))).read_text().splitlines()
        assert len(lines)==len(r['ink'])
        for ink in r['ink']:
            assert ink['target']=='complete_line';keys.append(ink['field']);count+=ink['words']>=5
        assert len(keys)==len(set(keys))
    for a,b in [('train','val'),('train','test'),('val','test')]:assert not fonts[a]&fonts[b]
    assert count>=4000
