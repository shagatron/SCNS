"""Portable policy/recovery tests. Mocked Windows calls are NOT Windows evidence."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core import portable

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "scns_native_tools", ROOT / "scripts/windows/native.py"
)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def test_receipt_replace_and_cross_process_lock(tmp_path):
    path = tmp_path / "receipt.json"
    native.write(path, {"phase": "reserved", "uuid": "stable"})
    native.write(path, {"phase": "verified", "uuid": "stable"})
    assert json.loads(path.read_text()) == {"phase": "verified", "uuid": "stable"}
    lock = tmp_path / "journal.lock"
    with lock.open("a") as handle:
        portable.lock_file(handle)
        code = 'from pathlib import Path;from app.core.portable import lock_file;import sys\ntry:\n with Path(sys.argv[1]).open("a") as f:lock_file(f)\nexcept BlockingIOError:sys.exit(9)'
        result = subprocess.run(
            [sys.executable, "-c", code, str(lock)], check=False, capture_output=True
        )
        assert result.returncode == 9
    with lock.open("a") as handle:
        portable.lock_file(handle)


@pytest.mark.parametrize(
    "source,major,target,allowed",
    [
        ("3.5.2", 17, "3.5.2", True),
        ("3.5.2", 17, "3.6.1", True),
        ("3.6.1", 17, "3.5.2", False),
        ("3.5.2", 18, "3.6.1", False),
        ("3.4.0", 17, "3.6.1", False),
        ("3.5.2", 17, "3.7.0", False),
    ],
)
def test_version_bounds_do_not_guess_compatibility(source, major, target, allowed):
    if allowed:
        native.compatible({"server_major": 17, "postgis": source}, major, target)
    else:
        with pytest.raises(native.SafeError):
            native.compatible({"server_major": 17, "postgis": source}, major, target)


def test_backup_tamper_incomplete_and_private_hashes(tmp_path):
    files = tmp_path / "files"
    files.mkdir()
    (files / "database.dump").write_bytes(b"synthetic archive")
    report = {
        "format": "scns-native-backup-v1",
        "complete": False,
        "files": native.file_hashes(files),
    }
    native.write(tmp_path / "manifest.json", report)
    with pytest.raises(native.SafeError, match="Incomplete"):
        native.check_bundle(tmp_path)
    report["complete"] = True
    native.write(tmp_path / "manifest.json", report)
    assert native.check_bundle(tmp_path) == report
    (files / "database.dump").write_bytes(b"tampered archive")
    with pytest.raises(native.SafeError, match="hash"):
        native.check_bundle(tmp_path)


def test_symlinks_are_not_silently_followed(tmp_path):
    if os.name == "nt":
        return  # Actual native ACL/runtime checks exercise supported normal files.
    (tmp_path / "link").symlink_to("/etc/passwd")
    with pytest.raises(native.SafeError, match="Symlink"):
        native.file_hashes(tmp_path)


@pytest.mark.parametrize("key", ["revision", "tables", "sequences", "active_releases"])
def test_reconciliation_rejects_every_preservation_mismatch(key):
    before = {
        "revision": "0016_closures",
        "tables": {"accounts": {"rows": 1, "sha256": "hash"}},
        "sequences": [["release_seq", 8]],
        "active_releases": [["campus", "unknown-locally-obtained-uuid", "content", "artifact"]],
    }
    native.same_data(before, dict(before))
    with pytest.raises(native.SafeError):
        native.same_data(before, {**before, key: None})


def test_native_environment_ignores_root_dotenv_and_points_only_to_copy(tmp_path):
    config = {
        "database": {
            "user": "scns_native_nonce",
            "password": "synthetic-only",
            "host": "127.0.0.1",
            "port": 5432,
            "dbname": "scns_native_nonce",
        },
        "storage": str(tmp_path / "copy"),
        "settings": {"IMPORT_BYTE_LIMIT": "4096"},
    }
    env = native.environment(config, tmp_path)
    assert env["SCNS_ENV_FILE"] == str(tmp_path / "unused-do-not-create.env")
    assert env["STORAGE_ROOT"] == config["storage"]
    assert "scns_native_nonce" in env["DATABASE_URL"]
    assert env["PUBLIC_APP_URL"] == "http://localhost:5173"
    assert env["IMPORT_BYTE_LIMIT"] == "4096"


def test_command_failure_never_echoes_credentials(monkeypatch):
    monkeypatch.setattr(
        native.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 2, b"", b"password=synthetic-secret"),
    )
    with pytest.raises(native.SafeError) as error:
        native.run(["pg_restore", "synthetic-sensitive-argument"])
    assert "secret" not in str(error.value) and "sensitive" not in str(error.value)


def test_windows_decoder_refuses_non_windows_and_no_linux_fallback():
    from app.core.windows_sandbox import Job

    if os.name != "nt":
        with pytest.raises(RuntimeError, match="native Windows"):
            Job(decoder=True)


@pytest.mark.skipif(
    os.name != "nt",
    reason="Requires actual Windows DPAPI and filesystem DACLs, not Linux emulation",
)
def test_actual_windows_dpapi_and_private_acl(tmp_path):
    folder = tmp_path / "native-private"
    native.protect(folder)
    original = b"Synthetic roundtrip only; never an owner credential"
    encrypted = native.dpapi(original)
    assert original not in encrypted and native.dpapi(encrypted, decrypt=True) == original
    with pytest.raises(native.SafeError):
        native.dpapi(encrypted[:-8] + b"corrupt!", decrypt=True)


@pytest.mark.skipif(os.name != "nt", reason="Requires actual Windows AppContainer and Job Objects")
def test_actual_windows_decoder_boundary_and_job_kill():
    from app.core.windows_sandbox import Job, run_decoder

    assert json.loads(run_decoder(b"", probe=True)) == {
        "filesystem_denied": True,
        "filesystem_write_denied": True,
        "network_denied": True,
        "database_env_absent": True,
    }
    job = Job()
    process = subprocess.Popen(
        [sys.executable, "-c", "import time;time.sleep(60)"],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    try:
        job.assign(int(process._handle))
        job.close()
        assert process.wait(timeout=5) != 0
    finally:
        job.close()
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def test_standalone_native_cli_fails_closed_on_linux(tmp_path):
    if os.name == "nt":
        return
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/windows/native.py"),
            "start",
            "--state",
            str(tmp_path),
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1 and b"Windows PowerShell" in result.stderr
    assert not list(tmp_path.iterdir())


def test_powershell_and_app_paths_do_not_depend_on_fixed_installation():
    script = (ROOT / "scripts/windows/scns.ps1").read_text()
    assert "--frozen" in script and "npm ci" in script and "LOCALAPPDATA" in script
    assert "C:\\Program Files\\PostgreSQL" not in script
    for forbidden in ("seed-demo", "bootstrap-admin", "alembic upgrade", "down -v", "Remove-Item"):
        assert forbidden not in script
