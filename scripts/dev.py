"""Run both development services and terminate their process groups on exit."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
processes = []


def stop():
    for process in processes:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def interrupt(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupt)
    exit_code = 0
    try:
        for service in ("api", "web", "worker"):
            processes.append(subprocess.Popen(["make", service], cwd=root, start_new_session=True))
        while all(p.poll() is None for p in processes):
            time.sleep(.2)
        exit_code = next(p.returncode for p in processes if p.returncode is not None)
    except KeyboardInterrupt:
        pass
    finally:
        stop()
    sys.exit(exit_code)
