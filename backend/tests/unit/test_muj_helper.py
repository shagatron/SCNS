import hashlib

import pytest

from app.cli.indoor_demo import DemoError
from app.cli.muj import retain_original
from app.core.portable import is_private_file


def test_private_original_is_atomic_replayable_and_keeps_inconsistent_history(tmp_path):
    raw = b"owner-provided source fixture"
    checksum = hashlib.sha256(raw).hexdigest()
    target = tmp_path / (checksum + ".osm")
    retain_original(raw, target, checksum)
    assert target.read_bytes() == raw and is_private_file(target)
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


def test_original_helper_rechecks_correction_history_after_pending_preview_before_apply():
    from app.cli.muj import stage
    from app.services.muj_setup import ROOT

    class Client:
        session = {"grants": [{"campus_id": "source-campus", "permissions": ["user_admin"]}]}
        preflights = 0
        apply_calls = 0

        def request(self, method, path, *args, **kwargs):
            if path.endswith("/muj-setup"):
                self.preflights += 1
                if self.preflights > 1:
                    raise DemoError(
                        "V2 correction committed while the legacy worker preview was pending"
                    )
                return {"campus_id": "muj-campus", "draft_id": "target-draft"}
            if "/imports?" in path:
                return {"id": "job", "state": "uploaded"}
            if method == "GET" and path.endswith("/imports/job"):
                return {
                    "id": "job",
                    "state": "preview_ready",
                    "counts": {"invalid": 0, "conflict": 0},
                    "rows": [],
                    "preview_version": 5,
                }
            if path.endswith("/validate"):
                return {}
            if path.endswith("/apply"):
                self.apply_calls += 1
                raise AssertionError("Must not replay v1 after a concurrent correction")
            raise AssertionError("Unexpected helper action")

    client = Client()
    with pytest.raises(DemoError, match="V2 correction"):
        stage(client, ROOT, confirm=lambda _: "APPLY", sleep=lambda _: None)
    assert client.preflights == 2 and client.apply_calls == 0
