import hashlib
import json
import zipfile
from pathlib import Path
import pytest
from package_models import package


def fixture(tmp_path,name='reader/model.onnx',actual=b'model'):
    source=tmp_path/'source';source.mkdir();external=tmp_path/'weights';external.write_bytes(actual)
    if name=='reader/model.onnx':
        (source/'reader').mkdir();(source/name).symlink_to(external)
    raw=json.dumps(dict(files={name:dict(bytes=5,sha256=hashlib.sha256(b'model').hexdigest())})).encode()
    (source/'manifest.json').write_bytes(raw)
    return source,tmp_path/'pack.zip',hashlib.sha256(raw).hexdigest()


def test_manifest_first_and_symlinks_become_bytes(tmp_path):
    source,target,pin=fixture(tmp_path);result=package(source,target,pin)
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist()==['manifest.json','reader/model.onnx']
        assert archive.read('reader/model.onnx')==b'model'
    assert result['sha256']==hashlib.sha256(target.read_bytes()).hexdigest()
    assert target.with_suffix('.zip.sha256').is_file()


def test_existing_pack_is_preserved(tmp_path):
    source,target,pin=fixture(tmp_path);target.write_bytes(b'keep')
    with pytest.raises(FileExistsError):package(source,target,pin)
    assert target.read_bytes()==b'keep'


def test_existing_checksum_is_preserved_before_packaging(tmp_path):
    source,target,pin=fixture(tmp_path);checksum=target.with_suffix('.zip.sha256');checksum.write_text('keep')
    with pytest.raises(FileExistsError):package(source,target,pin)
    assert checksum.read_text()=='keep';assert not target.exists()


def test_wrong_manifest_is_rejected_before_writing(tmp_path):
    source,target,_=fixture(tmp_path)
    with pytest.raises(ValueError):package(source,target,'wrong')
    assert not target.exists();assert not target.with_suffix('.zip.partial').exists()


@pytest.mark.parametrize('name',['../escape','/escape','reader/../escape','reader\\escape'])
def test_unsafe_entries_leave_no_pack(tmp_path,name):
    source,target,pin=fixture(tmp_path,name=name)
    with pytest.raises(ValueError):package(source,target,pin)
    assert not target.exists();assert not target.with_suffix('.zip.partial').exists()


def test_corrupt_weights_leave_no_pack(tmp_path):
    source,target,pin=fixture(tmp_path,actual=b'wrong')
    with pytest.raises(ValueError):package(source,target,pin)
    assert not target.exists();assert not target.with_suffix('.zip.partial').exists()
