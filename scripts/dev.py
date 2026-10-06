"""Run both development services and terminate their process groups on exit."""
import os
import signal
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
processes = []


def stop(signum=None, frame=None):
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s, f: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        for service in ("api", "web"):
            processes.append(subprocess.Popen(["make", service], cwd=root, start_new_session=True))
        while all(p.poll() is None for p in processes):
            time.sleep(.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop()
