"""Portable policy/recovery tests. Mocked Windows calls are NOT Windows evidence."""

import importlib.util
import json
import os
import shutil
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
        ("3.5.2", 17, "3.5.1", False),
        ("3.5.2", 17, "ANY", False),
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


def test_acl_failure_preserves_stage_and_numeric_error_without_raw_output(monkeypatch):
    diagnostic = {
        "stage": "persist-dacl",
        "windows_error": 1314,
        "hresult": "0x80070522",
        "message": "password=must-not-escape",
        "path": "private-account-directory",
    }
    stderr = b"private tool output\nSCNS_ACL_ERROR " + json.dumps(diagnostic).encode()
    monkeypatch.setattr(
        native.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 1, b"", stderr)
    )
    with pytest.raises(native.SafeError) as error:
        native.run(["pwsh", "private-argument"], stage="protect-state-directory")
    text = str(error.value)
    assert all(
        value in text for value in ["protect-state-directory", "persist-dacl", "1314", "0x80070522"]
    )
    assert not any(
        value in text
        for value in ["must-not-escape", "private-account", "private tool", "private-argument"]
    )


@pytest.mark.parametrize(
    "value",
    [
        [],
        {"stage": []},
        {"stage": "password=secret"},
        {"stage": "persist-dacl", "windows_error": True, "hresult": "0x80070005"},
        {"stage": "persist-dacl", "windows_error": -1, "hresult": "0x80070005"},
        {"stage": "persist-dacl", "windows_error": 5, "hresult": "password=secret"},
    ],
)
def test_acl_diagnostic_refuses_untrusted_or_malformed_details(value):
    assert native.acl_diagnostic(b"SCNS_ACL_ERROR " + json.dumps(value).encode()) == ""
    assert native.acl_diagnostic(b"SCNS_ACL_ERROR {bad json password=secret}") == ""


def test_acl_diagnostic_empty_and_unstructured_errors_remain_sanitized(monkeypatch):
    monkeypatch.setattr(
        native.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 5, b"", b"password=secret"),
    )
    with pytest.raises(native.SafeError, match="grant-decoder-runtime-read") as error:
        native.run(["icacls", "private-path"], stage="grant-decoder-runtime-read")
    assert "exit 5" in str(error.value)
    assert "secret" not in str(error.value) and "private-path" not in str(error.value)


def test_powershell_contracts_and_reuse_dependency_branch(tmp_path):
    pwsh = os.environ.get("SCNS_TEST_PWSH") or shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell parser/portable mocked-command harness unavailable")
    result = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(ROOT / "scripts/windows/script-contracts.ps1")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Portable script contracts passed" in result.stdout
    invalid = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-File",
            str(ROOT / "scripts/windows/scns.ps1"),
            "Start",
            "-ReuseDependencies",
            "-State",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode != 0 and "valid only with Setup" in invalid.stderr


@pytest.mark.skipif(
    os.name != "nt", reason="Requires actual non-elevated Windows filesystem ACL persistence"
)
def test_actual_windows_non_elevated_repeat_and_decoder_dacl(tmp_path):
    native.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(ROOT / "scripts/windows/acl.test.ps1"),
            "-Root",
            str(tmp_path),
        ],
        stage="test-private-dacl-fixture",
    )


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
    from app.core.portable import is_private_file, private_file

    folder = tmp_path / "native-private"
    native.protect(folder)
    original = b"Synthetic roundtrip only; never an owner credential"
    encrypted = native.dpapi(original)
    assert original not in encrypted and native.dpapi(encrypted, decrypt=True) == original
    native.save_secret(folder / "config.json", {"synthetic": original.decode()})
    assert original not in (folder / "config.json").read_bytes()
    assert native.load_secret(folder / "config.json") == {"synthetic": original.decode()}
    assert is_private_file(folder / "config.json")
    synthetic = tmp_path / "synthetic-acl-no-credentials.txt"
    synthetic.write_text("Synthetic ACL test only, no secret.")
    native.run(["icacls", str(synthetic), "/grant", "*S-1-1-0:(R)"])
    assert not is_private_file(synthetic)
    private_file(synthetic)
    assert is_private_file(synthetic)
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
    import tempfile

    with tempfile.TemporaryFile() as output:
        process = job.spawn(
            [sys.executable, "-c", "import time;time.sleep(60)"],
            cwd=ROOT / "backend",
            env={
                key: value
                for key, value in os.environ.items()
                if key.upper() in {"SYSTEMROOT", "PATH", "TEMP", "TMP"}
            },
            stdout=output,
        )
        try:
            job.close()
            assert process.wait(timeout=5) != 0
        finally:
            job.close()
            process.wait(timeout=5)
            process.close()


def test_decoder_uses_direct_base_interpreter_without_a_venv_child(tmp_path, monkeypatch):
    from app.core.windows_sandbox import decoder_command

    base = tmp_path / "Runtime with spaces and owner's quote"
    base.mkdir()
    executable = base / "python.exe"
    executable.write_bytes(b"not executed, policy fixture only")
    monkeypatch.setattr(sys, "base_prefix", str(base))
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "venv with spaces"))
    args = decoder_command()
    assert args[0] == str(executable) and args[1:6] == ["-I", "-B", "-X", "utf8", "-c"]
    assert "Lib/site-packages" in args[-1].replace("\\\\", "/")
    compile(args[-1], "<decoder-bootstrap>", "exec")
    executable.unlink()
    with pytest.raises(RuntimeError, match="no redirector"):
        decoder_command()


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


def test_inventory_is_read_only_and_does_not_save_container_secrets(tmp_path, monkeypatch, capsys):
    calls = []

    def command(args, **kwargs):
        calls.append(args)
        if args[0] == "git":
            return b"synthetic-head"
        if "inspect" in args:
            return json.dumps(
                [
                    {
                        "Config": {
                            "Env": [
                                "DATABASE_URL=synthetic-secret-never-echo",
                                "APP_ENV=development",
                            ]
                        },
                        "Mounts": [
                            {
                                "Type": "volume",
                                "Name": "retained-private",
                                "Source": "retained",
                                "Destination": "/app/storage",
                            }
                        ],
                    }
                ]
            ).encode()
        return b"retained-container-id"

    monkeypatch.setattr(native, "run", command)
    monkeypatch.setattr(native, "verify_source_binding", lambda actual: None)
    monkeypatch.setattr(
        native,
        "docker_inventory",
        lambda: {
            "tables": {},
            "revision": "0016_closures",
            "active_releases": [["actual-local-fixture-release-id"]],
        },
    )
    native.source_inventory(tmp_path)
    report = (tmp_path / "docker-inventory.json").read_text()
    assert "synthetic-secret" not in report + capsys.readouterr().out
    assert "DATABASE_URL" in report and "actual-local-fixture-release-id" in report
    assert not any("stop" in args or "run" in args or "up" in args for args in calls)


@pytest.mark.parametrize(
    "override",
    [
        {"STORAGE_ROOT": "/unmapped/private"},
        {"DATABASE_URL": "postgresql://owner:synthetic@other-host/scns"},
        {"DATABASE_URL": "postgresql://owner:synthetic@db/other-data"},
    ],
)
def test_source_binding_rejects_substitute_dataset_or_omitted_storage(monkeypatch, override):
    api = {
        "Config": {
            "Env": [
                f"{key}={value}"
                for key, value in {
                    "STORAGE_ROOT": "/app/storage",
                    "DATABASE_URL": "postgresql://owner:synthetic@db/scns",
                    **override,
                }.items()
            ]
        },
        "Mounts": [],
    }
    calls = []

    def command(args, **kwargs):
        calls.append(args)
        if "inspect" in args:
            return json.dumps([{"Config": {"Env": ["POSTGRES_DB=scns"]}}]).encode()
        return b"db-id" if args[-1] == "db" else b""

    monkeypatch.setattr(native, "run", command)
    with pytest.raises(native.SafeError):
        native.verify_source_binding(api)
    assert not any("stop" in args or "up" in args for args in calls)
