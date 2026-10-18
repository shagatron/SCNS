"""Cross-platform receipt durability and advisory locks (no API/auth changes)."""

import os
from pathlib import Path


def lock_file(handle):
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write("\0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise BlockingIOError("Another process owns this journal") from error
    else:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def private_file(path):
    path = Path(path)
    if os.name == "nt":
        from app.core.windows_sandbox import protect_owner_file

        protect_owner_file(path)
    else:
        path.chmod(0o600)


def private_directory(path):
    path = Path(path)
    if os.name == "nt":
        from app.core.windows_sandbox import protect_owner_file

        protect_owner_file(path, directory=True)
    else:
        path.chmod(0o700)


def is_private_file(path):
    path = Path(path)
    if os.name == "nt":
        from app.core.windows_sandbox import owner_private

        return path.is_file() and owner_private(path)
    return path.is_file() and path.stat().st_mode & 0o777 == 0o600


def private_mode(handle, path=None):
    if os.name == "nt":
        private_file(path or handle.name)
    else:
        os.fchmod(handle.fileno(), 0o600)


def durable_replace(temp, target):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        move = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        move.restype = wintypes.BOOL
        if not move(str(temp), str(target), 0x1 | 0x8):  # replace + WRITE_THROUGH
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.replace(temp, target)
        directory = os.open(target.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
