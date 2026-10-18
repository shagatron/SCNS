"""Portable failure-injection tests; never evidence of actual Windows isolation."""

import ctypes as c
import json
import os
import sys
import threading
from types import SimpleNamespace

import pytest

from app.core import windows_sandbox as sandbox


@pytest.fixture
def native_model(monkeypatch):
    state = SimpleNamespace(events=[], error=203, fail=None, inherited=[], child_fd=None)
    monkeypatch.setattr(c, "get_last_error", lambda: state.error, raising=False)
    monkeypatch.setattr(sandbox, "dll", lambda name: object())
    monkeypatch.setattr(sandbox, "profile_sid", lambda: 301)
    monkeypatch.setattr(sandbox, "free_sid", lambda sid: state.events.append(("free-sid", sid)))
    monkeypatch.setattr(sandbox, "protect_owner_file", lambda path: None)
    # Windows TemporaryFile has a path; Linux's anonymous file has only an fd.
    monkeypatch.setattr(sandbox.tempfile, "TemporaryFile", sandbox.tempfile.NamedTemporaryFile)
    monkeypatch.setattr(sandbox, "decoder_command", lambda **kw: ["python.exe", "-I"])
    monkeypatch.setattr(
        os, "set_handle_inheritable", lambda h, v: state.inherited.append((h, v)), raising=False
    )
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(get_osfhandle=lambda fd: fd))
    monkeypatch.setenv("SystemRoot", "synthetic-runtime")
    monkeypatch.setenv("DATABASE_URL", "password=must-not-print")

    def function(lib, name, args, result=None):
        def call(*values):
            state.events.append((name,))
            if name == "InitializeProcThreadAttributeList" and values[0] is None:
                state.error = 203 if state.fail == "size" else 122
                values[-1]._obj.value = 0 if state.fail == "size" else 256
                return 0
            state.error = 203
            key = name
            if name == "UpdateProcThreadAttribute":
                key += f".{values[2]:x}"
                if values[2] == 0x20009:
                    caps = values[3]._obj
                    assert caps.sid == 301 and caps.count == 0 and caps.capabilities is None
                else:
                    assert values[2] == 0x20002 and len(values[3]) == 3
                    state.handles = list(values[3])
            if state.fail == key:
                return 0xFFFFFFFF if name in {"WaitForSingleObject", "ResumeThread"} else 0
            if name == "CreateJobObjectW":
                return 601
            if name == "SetInformationJobObject":
                limits = values[2]._obj
                assert limits.basic.flags == 0x2000 | 0x100 | 0x8 | 0x2 | 0x400
                assert limits.basic.cpu == 20 * 10_000_000 and limits.basic.processes == 1
                assert limits.process_memory == limits.job_memory == 1024**3
            elif name == "GetCurrentProcess":
                return -1
            elif name == "DuplicateHandle":
                assert values[4:] == (0x80000000, True, 0)
                values[3]._obj.value = 201
            elif name == "CreateProcessW":
                assert values[4] is True
                assert values[5] == 0x80000 | 0x400 | 0x4 | 0x08000000
                assert "password=" not in "".join(values[6])
                values[-1]._obj.process, values[-1]._obj.thread = 501, 502
                state.child_fd = os.dup(state.handles[1])
            elif name == "AssignProcessToJobObject":
                assert values == (601, 501)
            elif name == "ResumeThread":
                assert ("AssignProcessToJobObject",) in state.events
                os.write(state.child_fd, b'{"synthetic":true}')
                os.close(state.child_fd)
                state.child_fd = None
            elif name == "WaitForSingleObject":
                return 0
            elif name == "GetExitCodeProcess":
                values[1]._obj.value = 0
            elif name == "CloseHandle":
                state.error = 999  # Cleanup cannot replace the original captured 203.
            return 1

        return call

    monkeypatch.setattr(sandbox, "function", function)
    yield state
    if state.child_fd is not None:
        os.close(state.child_fd)


def test_complete_launch_model_retains_security_and_closes_resources(native_model):
    records = []
    with sandbox.diagnostics(records.append):
        assert sandbox.run_decoder(b"synthetic") == b'{"synthetic":true}'
    assert len(native_model.inherited) == 3 and all(v for _, v in native_model.inherited)
    assert ("DeleteProcThreadAttributeList",) in native_model.events
    assert ("free-sid", 301) in native_model.events
    assert {
        "event": "passed",
        "operation": "process-result",
        "stage": "process-result",
    } in records
    assert records[-1] == {
        "event": "passed",
        "operation": "decoder-resource-cleanup",
        "stage": "decoder-resource-cleanup",
    }
    assert "must-not-print" not in json.dumps(records)


@pytest.mark.parametrize(
    "failure,operation,stage,initialized",
    [
        ("CreateJobObjectW", "CreateJobObjectW", "job-create-limits", False),
        ("SetInformationJobObject", "SetInformationJobObject", "job-create-limits", False),
        ("DuplicateHandle", "DuplicateHandle.read-only-input", "input-handle-duplicate", False),
        ("size", "InitializeProcThreadAttributeList.size", "attributes-initialize", False),
        (
            "InitializeProcThreadAttributeList",
            "InitializeProcThreadAttributeList",
            "attributes-initialize",
            False,
        ),
        (
            "UpdateProcThreadAttribute.20009",
            "UpdateProcThreadAttribute.security-capabilities",
            "attributes-security-capabilities",
            True,
        ),
        (
            "UpdateProcThreadAttribute.20002",
            "UpdateProcThreadAttribute.handle-list",
            "attributes-handle-list",
            True,
        ),
        ("CreateProcessW", "CreateProcessW", "process-create-suspended", True),
        ("AssignProcessToJobObject", "AssignProcessToJobObject", "job-assign-before-resume", True),
        ("ResumeThread", "ResumeThread", "process-resume", True),
        ("WaitForSingleObject", "WaitForSingleObject", "process-wait", True),
        ("GetExitCodeProcess", "GetExitCodeProcess", "process-result", True),
    ],
)
def test_same_203_is_attributed_to_actual_failed_call_and_cleanup(
    native_model, failure, operation, stage, initialized
):
    native_model.fail = failure
    with pytest.raises(sandbox.SandboxFailure) as error:
        sandbox.run_decoder(b"synthetic")
    assert error.value.record == {"stage": stage, "operation": operation, "windows_error": 203}
    assert (("DeleteProcThreadAttributeList",) in native_model.events) is initialized
    assert ("free-sid", 301) in native_model.events
    names = [e[0] for e in native_model.events]
    if failure in {"size", "InitializeProcThreadAttributeList"}:
        assert "CreateProcessW" not in names
    if failure == "AssignProcessToJobObject":
        assert "ResumeThread" not in names and "TerminateProcess" in names
    if failure == "WaitForSingleObject":
        assert "GetExitCodeProcess" not in names


def test_python_os_failure_stage_never_uses_stale_get_last_error(monkeypatch):
    monkeypatch.setattr(c, "get_last_error", lambda: 203, raising=False)
    with pytest.raises(sandbox.SandboxFailure) as error:
        with sandbox.stage("handle-inheritance"):
            raise OSError("password=private C:/private/file")
    assert error.value.record == {"stage": "handle-inheritance", "operation": "handle-inheritance"}
    assert "private" not in str(error.value) and "203" not in str(error.value)
    cause = OSError("must-not-print")
    cause.winerror = 5
    with pytest.raises(sandbox.SandboxFailure) as error:
        with sandbox.stage("input-file-create"):
            raise cause
    assert error.value.record["windows_error"] == 5


def test_hresult_uses_returned_code_not_stale_last_error(monkeypatch):
    monkeypatch.setattr(c, "get_last_error", lambda: 203, raising=False)
    with pytest.raises(sandbox.SandboxFailure) as error:
        sandbox.hresult(-2147024891, "GetAppContainerFolderPath")  # 0x80070005
    assert error.value.record["windows_error"] == 5
    assert error.value.record["hresult"] == 0x80070005
    with pytest.raises(sandbox.SandboxFailure) as error:
        sandbox.hresult(0x80004005, "CreateAppContainerProfile")
    assert "windows_error" not in error.value.record


def test_environment_allowlist_sort_termination_and_missing_value(monkeypatch):
    monkeypatch.setenv("SystemRoot", "synthetic-only")
    monkeypatch.setenv("PATH", "private-path")
    monkeypatch.setenv("DATABASE_URL", "private-password")
    text = "".join(sandbox.decoder_environment())
    assert text.endswith("\0\0")
    assert text.rstrip("\0").split("\0") == [
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONUTF8=1",
        "SystemRoot=synthetic-only",
    ]
    monkeypatch.delenv("SystemRoot")
    with pytest.raises(sandbox.SandboxFailure, match="SystemRoot.required") as error:
        sandbox.decoder_environment()
    assert "windows_error" not in error.value.record


def test_diagnostic_profile_lookup_never_creates_or_grants(monkeypatch):
    calls = []
    monkeypatch.setattr(sandbox, "dll", lambda name: None)

    def function(lib, name, args, result):
        calls.append(name)

        def call(*values):
            values[-1]._obj.value = 301
            return 0

        return call

    monkeypatch.setattr(sandbox, "function", function)
    with sandbox.diagnostics(lambda record: None):
        assert sandbox.profile_sid().value == 301
    assert calls == ["DeriveAppContainerSidFromAppContainerName"]


def test_wait_timeout_and_unexpected_status_fail_closed():
    with pytest.raises(sandbox.SandboxFailure, match="wall-or-output-budget"):
        sandbox.wait_decoder(lambda *a: 258, 1, timeout=0, overflow=threading.Event())
    with pytest.raises(sandbox.SandboxFailure, match="unexpected-result"):
        sandbox.wait_decoder(lambda *a: 7, 1, timeout=1, overflow=threading.Event())


def test_cleanup_failure_preserves_primary_native_operation(native_model, monkeypatch):
    cause = OSError("private path and credentials never printed")
    cause.winerror = 6

    def fail_cleanup(sid):
        raise cause

    monkeypatch.setattr(sandbox, "free_sid", fail_cleanup)
    native_model.fail = "CreateProcessW"
    records = []
    with sandbox.diagnostics(records.append), pytest.raises(sandbox.SandboxFailure) as error:
        sandbox.run_decoder(b"synthetic")
    assert error.value.record == {
        "stage": "process-create-suspended",
        "operation": "CreateProcessW",
        "windows_error": 203,
    }
    assert records[-1] == {
        "event": "cleanup-failed",
        "stage": "decoder-resource-cleanup",
        "operation": "decoder-resource-cleanup",
        "windows_error": 6,
    }
    assert "private" not in str(error.value) + json.dumps(records)


def test_failed_collector_start_cleans_up_without_join_masking(native_model, monkeypatch):
    def fail_start(self):
        raise RuntimeError("private exception message")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    with pytest.raises(sandbox.SandboxFailure) as error:
        sandbox.run_decoder(b"synthetic")
    assert error.value.record == {"stage": "process-resume", "operation": "process-resume"}
    assert ("ResumeThread",) not in native_model.events
    assert ("TerminateProcess",) in native_model.events
    assert ("free-sid", 301) in native_model.events


def test_canary_protection_failure_is_named_and_never_launches(native_model, monkeypatch):
    cause = OSError("private canary path")
    cause.winerror = 203

    def fail_protect(path):
        raise cause

    monkeypatch.setattr(sandbox, "protect_owner_file", fail_protect)
    with pytest.raises(sandbox.SandboxFailure) as error:
        sandbox.run_decoder(b"", probe=True)
    assert error.value.record == {
        "stage": "probe-canary-protect",
        "operation": "probe-canary-protect",
        "windows_error": 203,
    }
    assert not native_model.events
