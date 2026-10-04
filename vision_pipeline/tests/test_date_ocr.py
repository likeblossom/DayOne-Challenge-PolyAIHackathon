import json
from collections import defaultdict
import pytest
from vision_pipeline.date_ocr.normalize import parse_date
from vision_pipeline.date_ocr.common import DATASET

@pytest.mark.parametrize('raw,value',[('1st December 2025','2025-12-01'),('1er décembre 2025','2025-12-01'),('١ ديسمبر ٢٠٢٥','2025-12-01'),('02/13/2025','2025-02-13'),('2025-02-13','2025-02-13'),('February 13, 2025','2025-02-13'),('29/02/2024','2024-02-29')])
def test_complete_dates(raw,value):assert parse_date(raw)['value']==value

def test_ambiguity_is_not_silently_resolved():
    assert parse_date('03/04/2025')['value'] is None
    assert parse_date('03/04/2025','DMY')['value']=='2025-04-03'
    assert parse_date('03/04/2025','MDY')['value']=='2025-03-04'
    assert 'AMBIGUOUS_CENTURY' in parse_date('01/01/12')['issues']
    partial=parse_date('1st December');assert partial['value'] is None
    assert partial['components']==dict(year=None,month=12,day=1)
    assert parse_date('1010212026')['value'] is None
    assert parse_date('31/02/2025')['value'] is None

def test_date_dataset_is_font_and_date_disjoint():
    rows=[json.loads(s) for s in (DATASET/'labels.jsonl').read_text().splitlines()]
    dates=defaultdict(set);fonts=defaultdict(set)
    for r in rows:dates[r['split']].add(r['source_date']);fonts[r['split']].add(r['font'])
    for a,b in [('train','val'),('train','test'),('val','test')]:
        assert not dates[a]&dates[b];assert not fonts[a]&fonts[b]
    assert len(rows)==7200

def test_complete_dataset_labels_normalize_with_explicit_order():
    for line in (DATASET/'labels.jsonl').read_text().splitlines():
        row=json.loads(line)
        order=row['date_order'] if row['date_order'] in ['DMY','MDY'] else None
        parsed=parse_date(row['text'],order)
        if row['format'] in ['numeric','written_month']:
            assert parsed['value']==row['source_date'],(row,parsed)
        else:
            assert parsed['value'] is None,(row,parsed)
