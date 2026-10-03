import json

from midwife_extractor.storage import file_sha256, save_result_bundle


def test_bundle_keeps_image_and_records_integrity(tmp_path):
    source = tmp_path / "capture.png"
    source.write_bytes(b"synthetic-image-bytes")
    output = tmp_path / "record" / "result.json"

    json_path, image_path = save_result_bundle({"form_id": "example"}, source, output)

    assert json_path.exists()
    assert image_path.exists()
    assert image_path.read_bytes() == source.read_bytes()
    payload = json.loads(json_path.read_text())
    assert payload["source_image"]["filename"] == image_path.name
    assert payload["source_image"]["sha256"] == file_sha256(source)
    assert payload["source_image"]["original_filename"] == "capture.png"
    assert payload["source_image"]["modified"] is False
