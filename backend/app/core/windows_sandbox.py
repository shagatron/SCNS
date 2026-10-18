"""Native Windows decoder isolation. No capabilities, credentials or open paths.

AppContainer restricts filesystem/network; a Job Object bounds CPU/memory/processes.
Unlike Linux seccomp it permits read-only runtime files and its own isolated profile
directory. Neither profile nor runtime may contain application secrets. Fail closed
on ANY setup error. Windows acceptance must exercise the actual OS, not mocks.
"""

import ctypes as c
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes as w
from pathlib import Path

PROFILE = "SCNS.Decoder.v1"
LIMIT = 24 * 1024**2


def dll(name):
    if os.name != "nt":
        raise RuntimeError("Windows security APIs require native Windows")
    return c.WinDLL(name, use_last_error=True)


def function(lib, name, args, result=w.BOOL):
    fn = getattr(lib, name)
    fn.argtypes, fn.restype = args, result
    return fn


def checked(value):
    if not value:
        raise c.WinError(c.get_last_error())
    return value


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
            raise RuntimeError(
                f"AppContainer profile creation refused (HRESULT {status & 0xFFFFFFFF:08x})"
            )
        derive = function(
            env,
            "DeriveAppContainerSidFromAppContainerName",
            [w.LPCWSTR, c.POINTER(c.c_void_p)],
            c.c_long,
        )
        if derive(PROFILE, c.byref(sid)):
            raise RuntimeError("Cannot derive decoder AppContainer SID")
    return sid


def sid_text(sid):
    text = w.LPWSTR()
    checked(
        function(dll("advapi32"), "ConvertSidToStringSidW", [c.c_void_p, c.POINTER(w.LPWSTR)])(
            sid, c.byref(text)
        )
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
        if status:
            raise RuntimeError("Cannot find decoder profile directory")
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
        )
    )
    try:
        size = w.DWORD()
        info = function(
            a, "GetTokenInformation", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]
        )
        info(token, 1, None, 0, c.byref(size))
        buffer = c.create_string_buffer(size.value)
        checked(info(token, 1, buffer, size, c.byref(size)))
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
        raise c.WinError(status)
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
            )
        )
        found = set()
        for index in range(info.count):
            ace = c.c_void_p()
            checked(
                function(a, "GetAce", [c.c_void_p, w.DWORD, c.POINTER(c.c_void_p)])(
                    dacl, index, c.byref(ace)
                )
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
        )
    )
    descriptor = c.c_void_p()
    try:
        size = w.DWORD()
        info = function(
            a, "GetTokenInformation", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]
        )
        info(token, 1, None, 0, c.byref(size))
        buffer = c.create_string_buffer(size.value)
        checked(info(token, 1, buffer, size, c.byref(size)))
        sid = c.cast(buffer, c.POINTER(c.c_void_p))[0]
        inheritance = "OICI" if directory else ""
        sddl = f"D:P(A;{inheritance};FA;;;SY)(A;{inheritance};FA;;;{sid_text(sid)})"
        checked(
            function(
                a,
                "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                [w.LPCWSTR, w.DWORD, c.POINTER(c.c_void_p), c.c_void_p],
            )(sddl, 1, c.byref(descriptor), None)
        )
        checked(
            function(a, "SetFileSecurityW", [w.LPCWSTR, w.DWORD, c.c_void_p])(
                str(path), 0x80000004, descriptor
            )
        )
    finally:
        function(k, "CloseHandle", [w.HANDLE])(token)
        if descriptor.value:
            function(k, "LocalFree", [c.c_void_p], c.c_void_p)(descriptor)


class Job:
    def __init__(self, *, decoder=False):
        self.k = dll("kernel32")
        self.handle = checked(
            function(self.k, "CreateJobObjectW", [c.c_void_p, w.LPCWSTR], w.HANDLE)(None, None)
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
                )(self.handle, 9, c.byref(limits), c.sizeof(limits))
            )
        except BaseException:
            self.close()
            raise

    def assign(self, process):
        checked(
            function(self.k, "AssignProcessToJobObject", [w.HANDLE, w.HANDLE])(self.handle, process)
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
                )
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
            function(dll("kernel32"), "GenerateConsoleCtrlEvent", [w.DWORD, w.DWORD])(1, self.pid)
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
            initialize(None, 2, 0, c.byref(size))
            attributes = c.create_string_buffer(size.value)
            checked(initialize(attributes, 2, 0, c.byref(size)))
            update = function(
                k,
                "UpdateProcThreadAttribute",
                [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p],
            )
            jobs = (w.HANDLE * 1)(job.handle)
            checked(update(attributes, 0, 0x2000D, jobs, c.sizeof(jobs), None, None))
            checked(update(attributes, 0, 0x20002, handles, c.sizeof(handles), None, None))
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
                )
            )
            return OwnedProcess(process.process, process.pid)
    finally:
        if process.thread:
            function(k, "CloseHandle", [w.HANDLE])(process.thread)
        if attributes is not None:
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
        )
    )
    try:
        value, used = w.DWORD(), w.DWORD()
        checked(
            function(
                a,
                "GetTokenInformation",
                [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)],
            )(token, 29, c.byref(value), 4, c.byref(used))
        )
        limits = Extended()
        checked(
            function(
                k, "QueryInformationJobObject", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p]
            )(None, 9, c.byref(limits), c.sizeof(limits), None)
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


def run_decoder(payload, *, probe=False, probe_file=None, probe_port=None, timeout=30):
    """Create suspended, assign job BEFORE execution, inherit ONLY three handles."""
    if probe and probe_file is None:
        with (
            tempfile.TemporaryDirectory(prefix="scns-denied-") as folder,
            socket.socket() as listener,
        ):
            canary = Path(folder) / "owner-private.txt"
            canary.write_text("Synthetic owner-readable isolation canary; no secret.")
            protect_owner_file(canary)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            return run_decoder(
                payload,
                probe=True,
                probe_file=canary,
                probe_port=listener.getsockname()[1],
                timeout=timeout,
            )
    import msvcrt

    k = dll("kernel32")
    sid = profile_sid()
    job = Job(decoder=True)
    process = Process()
    attributes = None
    read_fd, write_fd = os.pipe()
    reader = os.fdopen(read_fd, "rb", buffering=0)
    data, done, overflow = bytearray(), threading.Event(), threading.Event()
    thread = None
    input_handle = w.HANDLE()

    def collect():
        try:
            while chunk := reader.read(min(65536, LIMIT + 1 - len(data))):
                data.extend(chunk)
                if len(data) > LIMIT:
                    overflow.set()
                    return
        finally:
            reader.close()
            done.set()

    try:
        with (
            tempfile.TemporaryFile() as source,
            # Pipe output is bounded in RAM; untrusted code gets no writable file.
            os.fdopen(write_fd, "wb", buffering=0) as output,
            open(os.devnull, "wb") as error,
        ):
            source.write(payload)
            source.seek(0)
            protect_owner_file(Path(source.name))
            current = function(k, "GetCurrentProcess", [], w.HANDLE)()
            checked(
                function(
                    k,
                    "DuplicateHandle",
                    [w.HANDLE, w.HANDLE, w.HANDLE, c.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD],
                )(
                    current,
                    msvcrt.get_osfhandle(source.fileno()),
                    current,
                    c.byref(input_handle),
                    0x80000000,
                    True,
                    0,
                )
            )
            handles = (w.HANDLE * 3)(
                input_handle.value,
                msvcrt.get_osfhandle(output.fileno()),
                msvcrt.get_osfhandle(error.fileno()),
            )
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            size = c.c_size_t()
            initialize = function(
                k,
                "InitializeProcThreadAttributeList",
                [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)],
            )
            initialize(None, 2, 0, c.byref(size))
            attributes = c.create_string_buffer(size.value)
            checked(initialize(attributes, 2, 0, c.byref(size)))
            update = function(
                k,
                "UpdateProcThreadAttribute",
                [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p],
            )
            caps = Capabilities(sid, None, 0, 0)
            checked(update(attributes, 0, 0x20009, c.byref(caps), c.sizeof(caps), None, None))
            checked(update(attributes, 0, 0x20002, handles, c.sizeof(handles), None, None))
            startup = StartupEx()
            startup.startup.cb = c.sizeof(startup)
            startup.startup.flags = 0x100
            startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
            startup.attributes = c.cast(attributes, c.c_void_p)
            # Minimal loader environment. No DB/session/proxy/native config secrets.
            env = {
                "SystemRoot": os.environ["SystemRoot"],
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUTF8": "1",
            }
            block = c.create_unicode_buffer(
                "\0".join(f"{key}={value}" for key, value in sorted(env.items())) + "\0\0"
            )
            argv = decoder_command(probe=probe, probe_file=probe_file, probe_port=probe_port)
            command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
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
                )
            )
            output.close()
            job.assign(process.process)
            thread = threading.Thread(target=collect, daemon=True)
            thread.start()
            checked(function(k, "ResumeThread", [w.HANDLE], w.DWORD)(process.thread) != 0xFFFFFFFF)
            wait = function(k, "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)
            deadline = time.monotonic() + timeout
            while wait(process.process, 20) == 258:
                if time.monotonic() > deadline or overflow.is_set():
                    raise TimeoutError("Decoder exceeded wall/output budget")
            code = w.DWORD()
            checked(
                function(k, "GetExitCodeProcess", [w.HANDLE, c.POINTER(w.DWORD)])(
                    process.process, c.byref(code)
                )
            )
            if not done.wait(2) or code.value or len(data) > LIMIT:
                raise ValueError(
                    f"Native isolated decoder refused input (exit {code.value:#x}); check runtime ACLs and AppContainer support, never bypass isolation"
                )
            return bytes(data)
    finally:
        job.close()
        if process.process:
            function(k, "TerminateProcess", [w.HANDLE, w.UINT])(process.process, 1)
        for handle in (process.thread, process.process):
            if handle:
                function(k, "CloseHandle", [w.HANDLE])(handle)
        if input_handle.value:
            function(k, "CloseHandle", [w.HANDLE])(input_handle)
        if thread is None:
            reader.close()
        else:
            thread.join(timeout=2)
        if attributes is not None:
            function(k, "DeleteProcThreadAttributeList", [c.c_void_p], None)(attributes)
        free_sid(sid)
