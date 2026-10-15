import hashlib

import pytest

from app.cli.indoor_demo import DemoError
from app.cli.muj import retain_original


def test_private_original_is_atomic_replayable_and_keeps_inconsistent_history(tmp_path):
    raw = b"owner-provided source fixture"
    checksum = hashlib.sha256(raw).hexdigest()
    target = tmp_path / (checksum + ".osm")
    retain_original(raw, target, checksum)
    assert target.read_bytes() == raw and target.stat().st_mode & 0o777 == 0o600
    retain_original(raw, target, checksum)
    assert len(list(tmp_path.iterdir())) == 1
    target.write_bytes(b"interrupted earlier copy")
    retain_original(raw, target, checksum)
    assert target.read_bytes() == raw
    assert [p.read_bytes() for p in tmp_path.glob("*.retained-*")] == [b"interrupted earlier copy"]


def test_wrong_source_or_interrupted_replace_never_clobbers_retained_source(tmp_path, monkeypatch):
    import app.cli.muj as helper

    raw = b"verified"
    sha = hashlib.sha256(raw).hexdigest()
    target = tmp_path / "source.osm"
    target.write_bytes(b"existing retained data")
    with pytest.raises(DemoError, match="checksum"):
        retain_original(b"wrong", target, sha)
    assert target.read_bytes() == b"existing retained data"

    def fail(*args):
        raise OSError("simulated failed atomic replace")

    monkeypatch.setattr(helper.os, "replace", fail)
    with pytest.raises(OSError):
        retain_original(raw, target, sha)
    assert target.read_bytes() == b"existing retained data"
    assert not list(tmp_path.glob("*.partial"))
