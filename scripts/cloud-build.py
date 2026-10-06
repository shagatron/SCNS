"""Forward the configured egress proxy and CA trust into isolated local builds.

Proxy values are passed by environment name, never printed or written to files.
The optional CA bundle is mounted as a BuildKit secret, not copied into images.
TLS and package-lock verification stay enabled.
"""
import os
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
os.environ.setdefault("DOCKER_CONFIG", "/tmp/scns-docker")
args = ["docker", "build"]
hosts = set()
for name in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
    if os.environ.get(name):
        args += ["--build-arg", name]
        if name != "NO_PROXY":
            host = urlsplit(os.environ[name]).hostname
            if host:
                hosts.add(host)
for host in sorted(hosts):
    args += ["--add-host", f"{host}:{socket.gethostbyname(host)}"]
ca = os.environ.get("SSL_CERT_FILE")
if ca and Path(ca).is_file():
    args += ["--secret", f"id=ca_bundle,src={ca}"]
for service, file in [("api", "backend/Dockerfile"), ("frontend", "frontend/Dockerfile")]:
    subprocess.run([*args, "-t", f"scns-{service}", "-f", file, "."], cwd=root, check=True)
