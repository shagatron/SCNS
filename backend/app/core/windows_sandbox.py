"""Native Windows decoder isolation. No capabilities, credentials or open paths.

AppContainer restricts filesystem/network; a Job Object bounds CPU/memory/processes.
Unlike Linux seccomp it permits read-only runtime files and its own isolated profile
directory. Neither profile nor runtime may contain application secrets. Fail closed
on ANY setup error. Windows acceptance must exercise the actual OS, not mocks.
"""

import ctypes as c
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from ctypes import wintypes as w
from pathlib import Path

PROFILE = "SCNS.Decoder.v1"
LIMIT = 24 * 1024**2
_stage = ContextVar("decoder_stage", default="windows-security")
_report = ContextVar("decoder_report", default=None)


class SandboxFailure(RuntimeError):
    """Only source-defined operation names and numeric codes cross this boundary."""

    def __init__(self, operation, *, windows_error=None, hresult=None, exit_code=None):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,95}", operation):
            operation = "invalid-operation"
        self.record = {"stage": _stage.get(), "operation": operation}
        for name, code in (
            ("windows_error", windows_error),
            ("hresult", hresult),
            ("exit_code", exit_code),
        ):
            if type(code) is int and 0 <= code <= 0xFFFFFFFF:
                self.record[name] = code
        super().__init__("SCNS_DECODER_ERROR " + json.dumps(self.record, sort_keys=True))


def report(event, operation):
    sink = _report.get()
    if sink:
        sink({"event": event, "stage": _stage.get(), "operation": operation})


@contextmanager
def stage(name):
    token = _stage.set(name)
    try:
        report("begin", name)
        yield
        report("passed", name)
    except SandboxFailure:
        raise
    except Exception as error:
        # Never infer a Win32 error from errno, stale GetLastError, or raw text.
        raise SandboxFailure(name, windows_error=getattr(error, "winerror", None)) from None
    finally:
        _stage.reset(token)


@contextmanager
def diagnostics(sink):
    token = _report.set(sink)
    try:
        yield
    finally:
        _report.reset(token)


def dll(name):
    if os.name != "nt":
        raise RuntimeError("Windows security APIs require native Windows")
    return c.WinDLL(name, use_last_error=True)


def function(lib, name, args, result=w.BOOL):
    fn = getattr(lib, name)
    fn.argtypes, fn.restype = args, result
    return fn


def checked(value, operation):
    if not value:
        # Capture immediately, before logging/cleanup can replace the native code.
        code = c.get_last_error()
        raise SandboxFailure(operation, windows_error=code)
    report("passed", operation)
    return value


def sized(value, size, operation):
    """The documented size-query failure must be ERROR_INSUFFICIENT_BUFFER."""
    code = c.get_last_error()
    if value or code != 122 or not size.value:
        raise SandboxFailure(operation, windows_error=code if not value else None)
    report("size-available", operation)


def hresult(status, operation):
    if status:
        code = status & 0xFFFFFFFF
        raise SandboxFailure(
            operation,
            hresult=code,
            windows_error=(code & 0xFFFF) if code >> 16 == 0x8007 else None,
        )
    report("passed", operation)


class Basic(c.Structure):
    _fields_ = [
        ("cpu", c.c_int64),
        ("job_cpu", c.c_int64),
        ("flags", w.DWORD),
        ("min_ws", c.c_size_t),
        ("max_ws", c.c_size_t),
        ("processes", w.DWORD),
        ("affinity", c.c_size_t),
        ("priority", w.DWORD),
        ("scheduling", w.DWORD),
    ]


class IO(c.Structure):
    _fields_ = [
        (n, c.c_uint64)
        for n in ("read", "write", "other", "read_bytes", "write_bytes", "other_bytes")
    ]


class Extended(c.Structure):
    _fields_ = [
        ("basic", Basic),
        ("io", IO),
        ("process_memory", c.c_size_t),
        ("job_memory", c.c_size_t),
        ("peak_process", c.c_size_t),
        ("peak_job", c.c_size_t),
    ]


class Startup(c.Structure):
    _fields_ = [
        ("cb", w.DWORD),
        ("reserved", w.LPWSTR),
        ("desktop", w.LPWSTR),
        ("title", w.LPWSTR),
        *[(n, w.DWORD) for n in ("x", "y", "cx", "cy", "chars_x", "chars_y", "fill", "flags")],
        ("show", w.WORD),
        ("reserved_size", w.WORD),
        ("reserved_data", c.POINTER(c.c_byte)),
        ("stdin", w.HANDLE),
        ("stdout", w.HANDLE),
        ("stderr", w.HANDLE),
    ]


class StartupEx(c.Structure):
    _fields_ = [("startup", Startup), ("attributes", c.c_void_p)]


class Process(c.Structure):
    _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]


class Capabilities(c.Structure):
    _fields_ = [
        ("sid", c.c_void_p),
        ("capabilities", c.c_void_p),
        ("count", w.DWORD),
        ("reserved", w.DWORD),
    ]


def profile_sid():
    env = dll("userenv")
    sid = c.c_void_p()
    # Diagnostic runs must inspect the existing setup, never create/configure it.
    if _report.get() is not None:
        derive = function(
            env,
            "DeriveAppContainerSidFromAppContainerName",
            [w.LPCWSTR, c.POINTER(c.c_void_p)],
            c.c_long,
        )
        hresult(derive(PROFILE, c.byref(sid)), "DeriveAppContainerSidFromAppContainerName")
        return sid
    create = function(
        env,
        "CreateAppContainerProfile",
        [w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, c.c_void_p, w.DWORD, c.POINTER(c.c_void_p)],
        c.c_long,
    )
    status = create(
        PROFILE, PROFILE, "SCNS untrusted decoder; no network capabilities", None, 0, c.byref(sid)
    )
    if status != 0:
        # Derive only if profile already exists. Do not mask arbitrary creation failures.
        if status & 0xFFFFFFFF != 0x800700B7:
            hresult(status, "CreateAppContainerProfile")
        derive = function(
            env,
            "DeriveAppContainerSidFromAppContainerName",
            [w.LPCWSTR, c.POINTER(c.c_void_p)],
            c.c_long,
        )
        hresult(derive(PROFILE, c.byref(sid)), "DeriveAppContainerSidFromAppContainerName")
    report("passed", "CreateAppContainerProfile")
    return sid


def sid_text(sid):
    text = w.LPWSTR()
    checked(
        function(dll("advapi32"), "ConvertSidToStringSidW", [c.c_void_p, c.POINTER(w.LPWSTR)])(
            sid, c.byref(text)
        ),
        "ConvertSidToStringSidW",
    )
    try:
        return text.value
    finally:
        function(dll("kernel32"), "LocalFree", [c.c_void_p], c.c_void_p)(c.cast(text, c.c_void_p))


def free_sid(sid):
    function(dll("advapi32"), "FreeSid", [c.c_void_p], c.c_void_p)(sid)


def profile_folder():
    sid = profile_sid()
    try:
        path = w.LPWSTR()
        status = function(
            dll("userenv"), "GetAppContainerFolderPath", [w.LPCWSTR, c.POINTER(w.LPWSTR)], c.c_long
        )(sid_text(sid), c.byref(path))
        hresult(status, "GetAppContainerFolderPath")
        try:
            return Path(path.value)
        finally:
            function(dll("ole32"), "CoTaskMemFree", [c.c_void_p], None)(c.cast(path, c.c_void_p))
    finally:
        free_sid(sid)


def current_user_sid():
    k, a = dll("kernel32"), dll("advapi32")
    token = w.HANDLE()
    checked(
        function(a, "OpenProcessToken", [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)])(
            function(k, "GetCurrentProcess", [], w.HANDLE)(), 8, c.byref(token)
        ),
        "OpenProcessToken",
    )
    try:
        size = w.DWORD()
        info = function(
            a, "GetTokenInformation", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]
        )
        sized(info(token, 1, None, 0, c.byref(size)), size, "GetTokenInformation.size")
        buffer = c.create_string_buffer(size.value)
        checked(info(token, 1, buffer, size, c.byref(size)), "GetTokenInformation")
        return sid_text(c.cast(buffer, c.POINTER(c.c_void_p))[0])
    finally:
        function(k, "CloseHandle", [w.HANDLE])(token)


def owner_private(path):
    a, k = dll("advapi32"), dll("kernel32")
    dacl, descriptor, owner = c.c_void_p(), c.c_void_p(), c.c_void_p()
    status = function(
        a,
        "GetNamedSecurityInfoW",
        [
            w.LPWSTR,
            c.c_int,
            w.DWORD,
            c.POINTER(c.c_void_p),
            c.c_void_p,
            c.POINTER(c.c_void_p),
            c.c_void_p,
            c.POINTER(c.c_void_p),
        ],
        w.DWORD,
    )(str(path), 1, 5, c.byref(owner), None, c.byref(dacl), None, c.byref(descriptor))
    if status:
        raise SandboxFailure("GetNamedSecurityInfoW", windows_error=status)
    try:
        user = current_user_sid()
        if not dacl.value or sid_text(owner) not in {user, "S-1-5-18"}:
            return False

        class AclInfo(c.Structure):
            _fields_ = [("count", w.DWORD), ("used", w.DWORD), ("free", w.DWORD)]

        info = AclInfo()
        checked(
            function(a, "GetAclInformation", [c.c_void_p, c.c_void_p, w.DWORD, c.c_int])(
                dacl, c.byref(info), c.sizeof(info), 2
            ),
            "GetAclInformation",
        )
        found = set()
        for index in range(info.count):
            ace = c.c_void_p()
            checked(
                function(a, "GetAce", [c.c_void_p, w.DWORD, c.POINTER(c.c_void_p)])(
                    dacl, index, c.byref(ace)
                ),
                "GetAce",
            )
            if c.cast(ace, c.POINTER(c.c_ubyte))[0] != 0:
                return False
            identity = sid_text(c.c_void_p(ace.value + 8))
            mask = c.cast(c.c_void_p(ace.value + 4), c.POINTER(w.DWORD))[0]
            if identity not in {user, "S-1-5-18"} or mask & 0x1F01FF != 0x1F01FF:
                return False
            found.add(identity)
        return found == {user, "S-1-5-18"}
    finally:
        function(k, "LocalFree", [c.c_void_p], c.c_void_p)(descriptor)


def protect_owner_file(path, *, directory=False):
    """Protect generated input/probe files independent of TEMP's inherited ACL."""
    k, a = dll("kernel32"), dll("advapi32")
    token = w.HANDLE()
    checked(
        function(a, "OpenProcessToken", [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)])(
            function(k, "GetCurrentProcess", [], w.HANDLE)(), 8, c.byref(token)
        ),
        "OpenProcessToken",
    )
    descriptor = c.c_void_p()
    try:
        size = w.DWORD()
        info = function(
            a, "GetTokenInformation", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]
        )
        sized(info(token, 1, None, 0, c.byref(size)), size, "GetTokenInformation.size")
        buffer = c.create_string_buffer(size.value)
        checked(info(token, 1, buffer, size, c.byref(size)), "GetTokenInformation")
        sid = c.cast(buffer, c.POINTER(c.c_void_p))[0]
        inheritance = "OICI" if directory else ""
        sddl = f"D:P(A;{inheritance};FA;;;SY)(A;{inheritance};FA;;;{sid_text(sid)})"
        checked(
            function(
                a,
                "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                [w.LPCWSTR, w.DWORD, c.POINTER(c.c_void_p), c.c_void_p],
            )(sddl, 1, c.byref(descriptor), None),
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        )
        checked(
            function(a, "SetFileSecurityW", [w.LPCWSTR, w.DWORD, c.c_void_p])(
                str(path), 0x80000004, descriptor
            ),
            "SetFileSecurityW",
        )
    finally:
        function(k, "CloseHandle", [w.HANDLE])(token)
        if descriptor.value:
            function(k, "LocalFree", [c.c_void_p], c.c_void_p)(descriptor)


class Job:
    def __init__(self, *, decoder=False):
        self.k = dll("kernel32")
        self.handle = checked(
            function(self.k, "CreateJobObjectW", [c.c_void_p, w.LPCWSTR], w.HANDLE)(None, None),
            "CreateJobObjectW",
        )
        limits = Extended()
        limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE; children cannot escape.
        if decoder:
            limits.basic.flags |= 0x100 | 0x8 | 0x2 | 0x400
            limits.basic.cpu = 20 * 10_000_000
            limits.basic.processes = 1
            limits.process_memory = limits.job_memory = 1024**3
        try:
            checked(
                function(
                    self.k, "SetInformationJobObject", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
                )(self.handle, 9, c.byref(limits), c.sizeof(limits)),
                "SetInformationJobObject",
            )
        except BaseException:
            self.close()
            raise

    def assign(self, process):
        checked(
            function(self.k, "AssignProcessToJobObject", [w.HANDLE, w.HANDLE])(
                self.handle, process
            ),
            "AssignProcessToJobObject",
        )

    def spawn(self, args, *, cwd, env, stdout):
        return spawn_owned(self, args, cwd=cwd, env=env, stdout=stdout)

    def close(self):
        if self.handle:
            function(self.k, "CloseHandle", [w.HANDLE])(self.handle)
            self.handle = None


class OwnedProcess:
    """Small process interface with a job attached atomically at creation."""

    def __init__(self, handle, pid):
        self.handle, self.pid, self.returncode = handle, pid, None

    def poll(self):
        if self.returncode is None:
            result = function(dll("kernel32"), "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)(
                self.handle, 0
            )
            if result == 258:
                return None
            if result != 0:
                raise RuntimeError("Cannot inspect owned native process")
            code = w.DWORD()
            checked(
                function(dll("kernel32"), "GetExitCodeProcess", [w.HANDLE, c.POINTER(w.DWORD)])(
                    self.handle, c.byref(code)
                ),
                "GetExitCodeProcess",
            )
            self.returncode = code.value
        return self.returncode

    def wait(self, timeout=None):
        result = function(dll("kernel32"), "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)(
            self.handle, 0xFFFFFFFF if timeout is None else int(timeout * 1000)
        )
        if result == 258:
            raise subprocess.TimeoutExpired("owned-native-child", timeout)
        if result != 0:
            raise RuntimeError("Cannot wait for owned native process")
        return self.poll()

    def send_signal(self, signum):
        import signal

        if signum != signal.CTRL_BREAK_EVENT:
            raise ValueError("Only graceful owned-group break is supported")
        checked(
            function(dll("kernel32"), "GenerateConsoleCtrlEvent", [w.DWORD, w.DWORD])(1, self.pid),
            "GenerateConsoleCtrlEvent",
        )

    def close(self):
        if self.handle:
            function(dll("kernel32"), "CloseHandle", [w.HANDLE])(self.handle)
            self.handle = None


def spawn_owned(job, args, *, cwd, env, stdout):
    """JOB_LIST avoids a launcher spawning an unowned child before assignment."""
    import msvcrt

    k = dll("kernel32")
    attributes = None
    initialized = False
    process = Process()
    try:
        with open(os.devnull, "rb") as source:
            handles = (w.HANDLE * 2)(
                msvcrt.get_osfhandle(source.fileno()), msvcrt.get_osfhandle(stdout.fileno())
            )
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            size = c.c_size_t()
            initialize = function(
                k,
                "InitializeProcThreadAttributeList",
                [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)],
            )
            sized(
                initialize(None, 2, 0, c.byref(size)),
                size,
                "InitializeProcThreadAttributeList.size",
            )
            attributes = c.create_string_buffer(size.value)
            checked(
                initialize(attributes, 2, 0, c.byref(size)), "InitializeProcThreadAttributeList"
            )
            initialized = True
            update = function(
                k,
                "UpdateProcThreadAttribute",
                [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p],
            )
            jobs = (w.HANDLE * 1)(job.handle)
            checked(
                update(attributes, 0, 0x2000D, jobs, c.sizeof(jobs), None, None),
                "UpdateProcThreadAttribute",
            )
            checked(
                update(attributes, 0, 0x20002, handles, c.sizeof(handles), None, None),
                "UpdateProcThreadAttribute",
            )
            startup = StartupEx()
            startup.startup.cb = c.sizeof(startup)
            startup.startup.flags = 0x100
            startup.startup.stdin = handles[0]
            startup.startup.stdout = startup.startup.stderr = handles[1]
            startup.attributes = c.cast(attributes, c.c_void_p)
            block = c.create_unicode_buffer(
                "\0".join(
                    f"{key}={value}"
                    for key, value in sorted(env.items(), key=lambda pair: pair[0].upper())
                )
                + "\0\0"
            )
            command = c.create_unicode_buffer(subprocess.list2cmdline([str(arg) for arg in args]))
            create = function(
                k,
                "CreateProcessW",
                [
                    w.LPCWSTR,
                    w.LPWSTR,
                    c.c_void_p,
                    c.c_void_p,
                    w.BOOL,
                    w.DWORD,
                    c.c_void_p,
                    w.LPCWSTR,
                    c.c_void_p,
                    c.POINTER(Process),
                ],
            )
            checked(
                create(
                    str(args[0]),
                    command,
                    None,
                    None,
                    True,
                    0x80000 | 0x400 | 0x200,
                    block,
                    str(cwd),
                    c.byref(startup),
                    c.byref(process),
                ),
                "CreateProcessW",
            )
            return OwnedProcess(process.process, process.pid)
    finally:
        if process.thread:
            function(k, "CloseHandle", [w.HANDLE])(process.thread)
        if initialized:
            function(k, "DeleteProcThreadAttributeList", [c.c_void_p], None)(attributes)


def decoder_command(*, probe=False, probe_file=None, probe_port=None):
    # A Windows venv redirector may CreateProcess the actual Python interpreter.
    # Launch the base executable directly to keep the hard one-process boundary.
    executable = Path(sys.base_prefix) / "python.exe"
    if not executable.is_file():
        raise RuntimeError("Base Windows interpreter missing; no redirector/unrestricted fallback")
    paths = [str(Path(__file__).parents[2]), str(Path(sys.prefix) / "Lib/site-packages")]
    stub = f"import sys,runpy;sys.path[:0]={paths!r};runpy.run_module('app.cli.render_floorplan',run_name='__main__')"
    return [
        str(executable),
        "-I",
        "-B",
        "-X",
        "utf8",
        "-c",
        stub,
        *(
            [
                "--probe",
                "--probe-file",
                str(probe_file),
                "--probe-port",
                str(probe_port),
                "--probe-write-dir",
                str(profile_folder()),
            ]
            if probe
            else []
        ),
    ]


def assert_isolated():
    k, a = dll("kernel32"), dll("advapi32")
    current = function(k, "GetCurrentProcess", [], w.HANDLE)()
    token = w.HANDLE()
    checked(
        function(a, "OpenProcessToken", [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)])(
            current, 8, c.byref(token)
        ),
        "OpenProcessToken",
    )
    try:
        value, used = w.DWORD(), w.DWORD()
        checked(
            function(
                a,
                "GetTokenInformation",
                [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)],
            )(token, 29, c.byref(value), 4, c.byref(used)),
            "GetTokenInformation",
        )
        limits = Extended()
        checked(
            function(
                k, "QueryInformationJobObject", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p]
            )(None, 9, c.byref(limits), c.sizeof(limits), None),
            "QueryInformationJobObject",
        )
        if (
            not value.value
            or limits.basic.processes != 1
            or limits.process_memory != 1024**3
            or limits.job_memory != 1024**3
            or limits.basic.cpu != 20 * 10_000_000
            or not limits.basic.flags & 0x2000
        ):
            raise RuntimeError("Decoder token/job is not isolated")
    finally:
        function(k, "CloseHandle", [w.HANDLE])(token)


def decoder_environment():
    """Explicit allowlist; never copy PATH/TEMP, DB, session, proxy or config values."""
    with stage("environment-block"):
        root = os.environ.get("SystemRoot")
        if not root or "\0" in root:
            raise SandboxFailure("SystemRoot.required")
        env = {"SystemRoot": root, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        return c.create_unicode_buffer(
            "\0".join(
                f"{key}={value}" for key, value in sorted(env.items(), key=lambda p: p[0].upper())
            )
            + "\0\0"
        )


def wait_decoder(wait, process, *, timeout, overflow):
    deadline = time.monotonic() + timeout
    while True:
        result = wait(process, 20)
        if result == 0xFFFFFFFF:
            # WAIT_FAILED must not be hidden by GetExitCodeProcess/cleanup.
            raise SandboxFailure("WaitForSingleObject", windows_error=c.get_last_error())
        if result == 0:
            return
        if result != 258:
            raise SandboxFailure("WaitForSingleObject.unexpected-result")
        if time.monotonic() > deadline or overflow.is_set():
            raise SandboxFailure("process.wall-or-output-budget")


def run_decoder(payload, *, probe=False, probe_file=None, probe_port=None, timeout=30):
    """Create suspended, assign job BEFORE execution, inherit ONLY three handles."""
    from contextlib import ExitStack

    if probe and probe_file is None:
        with stage("probe-fixture-lifetime"), ExitStack() as resources:
            with stage("probe-canary-create"):
                folder = resources.enter_context(tempfile.TemporaryDirectory(prefix="scns-denied-"))
                canary = Path(folder) / "owner-private.txt"
                canary.write_text("Synthetic owner-readable isolation canary; no secret.")
            with stage("probe-canary-protect"):
                protect_owner_file(canary)
            with stage("probe-loopback-listener"):
                listener = resources.enter_context(socket.socket())
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
            return run_decoder(
                payload,
                probe=True,
                probe_file=canary,
                probe_port=listener.getsockname()[1],
                timeout=timeout,
            )
    with stage("windows-runtime-load"):
        import msvcrt

        k = dll("kernel32")
    sid = job = reader = attributes = None
    initialized = False
    write_fd = read_fd = None
    process = Process()
    data, done, overflow = bytearray(), threading.Event(), threading.Event()
    read_failed = threading.Event()
    thread = None
    thread_started = False
    input_handle = w.HANDLE()

    def collect():
        try:
            while chunk := reader.read(min(65536, LIMIT + 1 - len(data))):
                data.extend(chunk)
                if len(data) > LIMIT:
                    overflow.set()
                    return
        except OSError:
            read_failed.set()  # No raw exception from the collector thread.
        finally:
            reader.close()
            done.set()

    try:
        with stage("profile-lookup"):
            sid = profile_sid()
        with stage("job-create-limits"):
            job = Job(decoder=True)
        with stage("output-pipe-create"):
            read_fd, write_fd = os.pipe()
            reader = os.fdopen(read_fd, "rb", buffering=0)
            read_fd = None
        with stage("input-output-lifetime"), ExitStack() as resources:
            with stage("input-file-create"):
                source = resources.enter_context(tempfile.TemporaryFile())
            with stage("output-handles-open"):
                output = os.fdopen(write_fd, "wb", buffering=0)
                write_fd = None
                resources.enter_context(output)
                error = resources.enter_context(open(os.devnull, "wb"))
            with stage("input-file-write"):
                source.write(payload)
                source.seek(0)
            with stage("input-file-protect"):
                protect_owner_file(Path(source.name))
            with stage("input-handle-duplicate"):
                current = function(k, "GetCurrentProcess", [], w.HANDLE)()
                checked(
                    function(
                        k,
                        "DuplicateHandle",
                        [
                            w.HANDLE,
                            w.HANDLE,
                            w.HANDLE,
                            c.POINTER(w.HANDLE),
                            w.DWORD,
                            w.BOOL,
                            w.DWORD,
                        ],
                    )(
                        current,
                        msvcrt.get_osfhandle(source.fileno()),
                        current,
                        c.byref(input_handle),
                        0x80000000,
                        True,
                        0,
                    ),
                    "DuplicateHandle.read-only-input",
                )
            with stage("handle-inheritance"):
                handles = (w.HANDLE * 3)(
                    input_handle.value,
                    msvcrt.get_osfhandle(output.fileno()),
                    msvcrt.get_osfhandle(error.fileno()),
                )
                for handle in handles:
                    os.set_handle_inheritable(handle, True)
            with stage("attributes-initialize"):
                size = c.c_size_t()
                initialize = function(
                    k,
                    "InitializeProcThreadAttributeList",
                    [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)],
                )
                sized(
                    initialize(None, 2, 0, c.byref(size)),
                    size,
                    "InitializeProcThreadAttributeList.size",
                )
                attributes = c.create_string_buffer(size.value)
                checked(
                    initialize(attributes, 2, 0, c.byref(size)), "InitializeProcThreadAttributeList"
                )
                initialized = True
                update = function(
                    k,
                    "UpdateProcThreadAttribute",
                    [
                        c.c_void_p,
                        w.DWORD,
                        c.c_size_t,
                        c.c_void_p,
                        c.c_size_t,
                        c.c_void_p,
                        c.c_void_p,
                    ],
                )
            with stage("attributes-security-capabilities"):
                caps = Capabilities(sid, None, 0, 0)
                checked(
                    update(attributes, 0, 0x20009, c.byref(caps), c.sizeof(caps), None, None),
                    "UpdateProcThreadAttribute.security-capabilities",
                )
            with stage("attributes-handle-list"):
                checked(
                    update(attributes, 0, 0x20002, handles, c.sizeof(handles), None, None),
                    "UpdateProcThreadAttribute.handle-list",
                )
                startup = StartupEx()
                startup.startup.cb = c.sizeof(startup)
                startup.startup.flags = 0x100
                startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
                startup.attributes = c.cast(attributes, c.c_void_p)
            block = decoder_environment()
            with stage("decoder-command"):
                argv = decoder_command(probe=probe, probe_file=probe_file, probe_port=probe_port)
                command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
            with stage("process-create-suspended"):
                create = function(
                    k,
                    "CreateProcessW",
                    [
                        w.LPCWSTR,
                        w.LPWSTR,
                        c.c_void_p,
                        c.c_void_p,
                        w.BOOL,
                        w.DWORD,
                        c.c_void_p,
                        w.LPCWSTR,
                        c.c_void_p,
                        c.POINTER(Process),
                    ],
                )
                checked(
                    create(
                        argv[0],
                        command,
                        None,
                        None,
                        True,
                        0x80000 | 0x400 | 0x4 | 0x08000000,
                        block,
                        str(Path(__file__).parents[2]),
                        c.byref(startup),
                        c.byref(process),
                    ),
                    "CreateProcessW",
                )
            with stage("job-assign-before-resume"):
                output.close()
                job.assign(process.process)
            with stage("process-resume"):
                thread = threading.Thread(target=collect, daemon=True)
                thread.start()
                thread_started = True
                checked(
                    function(k, "ResumeThread", [w.HANDLE], w.DWORD)(process.thread) != 0xFFFFFFFF,
                    "ResumeThread",
                )
            with stage("process-wait"):
                wait = function(k, "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)
                wait_decoder(wait, process.process, timeout=timeout, overflow=overflow)
            with stage("process-result"):
                code = w.DWORD()
                checked(
                    function(k, "GetExitCodeProcess", [w.HANDLE, c.POINTER(w.DWORD)])(
                        process.process, c.byref(code)
                    ),
                    "GetExitCodeProcess",
                )
                if code.value:
                    raise SandboxFailure("decoder-child.exit", exit_code=code.value)
                if not done.wait(2) or read_failed.is_set() or len(data) > LIMIT:
                    raise SandboxFailure("decoder-child.output")
                return bytes(data)
    finally:
        primary = sys.exception()
        try:
            with stage("decoder-resource-cleanup"):
                if job is not None:
                    job.close()
                if process.process:
                    function(k, "TerminateProcess", [w.HANDLE, w.UINT])(process.process, 1)
                for handle in (process.thread, process.process, input_handle.value):
                    if handle:
                        function(k, "CloseHandle", [w.HANDLE])(handle)
                for fd in (read_fd, write_fd):
                    if fd is not None:
                        os.close(fd)
                if not thread_started:
                    if reader is not None:
                        reader.close()
                else:
                    thread.join(timeout=2)
                # A failed initialization does NOT produce a deletable attribute list.
                if initialized:
                    function(k, "DeleteProcThreadAttributeList", [c.c_void_p], None)(attributes)
                if sid is not None:
                    free_sid(sid)
        except SandboxFailure as cleanup_error:
            if primary is None:
                raise
            # Cleanup must never replace the operation/code that stopped launch.
            if _report.get():
                _report.get()({"event": "cleanup-failed", **cleanup_error.record})
