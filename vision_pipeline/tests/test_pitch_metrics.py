import json
from vision_pipeline.pitch_metrics import equal, distance, score_pages


def test_normalization_preserves_numeric_values():
    assert equal('Allaitement Exclusif.', 'allaitement exclusif', normalized=True)
    assert equal('Température', 'temperature', normalized=True)
    assert not equal(36.7, 367, normalized=True)
    assert not equal('51789', '5178g', normalized=True)
    assert not equal(None, '', normalized=True)
    assert equal(['A', 'B'], ['B', 'A'], normalized=True)


def test_edit_distance():
    assert distance('abc', 'adc') == 1
    assert distance([], ['a', 'b']) == 2


def test_raw_metrics_include_missing_ocr(tmp_path):
    path=tmp_path/'page_01'/'relative'; path.mkdir(parents=True)
    (path/'prediction.json').write_text(json.dumps({'fields': {
        'present': {'value': 36.7, 'raw_candidates': [{'text': '36.7 C'}]},
        'missing': {'value': None, 'raw_candidates': []}}}))
    truth={'pdf_page': 1, 'fields': {
        'present': {'score_eligible': True, 'kind': 'text', 'status': 'KNOWN', 'value': 36.7, 'raw_text': '36.7 C'},
        'missing': {'score_eligible': True, 'kind': 'text', 'status': 'KNOWN', 'value': 'abc', 'raw_text': 'abc'}}}
    result=score_pages([truth], tmp_path)
    assert result['counts']['filled_text'] == 2
    assert result['counts']['text_with_ocr'] == 1
    assert result['reference_characters'] == 9
    assert result['character_edits'] == 3
    assert result['raw_cer'] == 1/3
    assert result['raw_wer'] == 1/3
