import sys
from types import SimpleNamespace
from unittest.mock import mock_open

import pytest

from snowin.io import is_s3_uri, stage_remote_file


def test_is_s3_uri():
    assert is_s3_uri("s3://bucket/key.nc")
    assert not is_s3_uri("/tmp/key.nc")


def test_stage_remote_file_local_passthrough(tmp_path):
    f = tmp_path / "a.nc"
    f.write_text("x")
    assert stage_remote_file(f, tmp_path / "cache") == f.resolve()


def test_stage_remote_file_missing_local_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        stage_remote_file(tmp_path / "missing.nc", tmp_path / "cache")


def test_stage_remote_file_s3_uses_cache_when_existing(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    existing = cache / "file.nc"
    existing.write_bytes(b"abc")
    out = stage_remote_file("s3://bucket/file.nc", cache)
    assert out == existing.resolve()


def test_stage_remote_file_s3_mocked_download(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    read_handle = mock_open(read_data=b"abc").return_value
    fake_fsspec = SimpleNamespace(open=lambda *args, **kwargs: read_handle)
    monkeypatch.setitem(sys.modules, "fsspec", fake_fsspec)
    out = stage_remote_file("s3://bucket/path/file.nc", cache, overwrite=True)
    assert out.name == "file.nc"
    assert out.read_bytes() == b"abc"
