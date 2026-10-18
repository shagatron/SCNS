#!/usr/bin/env python3
"""Built nginx/API browser workflow on a fresh synthetic DB, never developer data.

Run after building both images and completing source browser checks (port 5174).
Requires existing Compose db; owns/removes only uniquely named test resources.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run(args, env=None):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    if result.returncode:
        # Never emit environment/credentials, command argv or private upload content.
        raise RuntimeError(f"Container smoke command failed ({args[0]}), exit {result.returncode}")
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--muj-only",
        action="store_true",
        help="Rerun just the affected MUJ desktop/mobile cases after a converter-only change",
    )
    selection.add_argument(
        "--explorer-only",
        action="store_true",
        help="Rerun affected explorer, source-visual and public-experience cases after a presentation-only change",
    )
    selection.add_argument(
        "--indoor-demo-only",
        action="store_true",
        help="Educational preview plus homepage, public navigation, indoor and admin regressions",
    )
    args = parser.parse_args()
    private = tempfile.TemporaryDirectory(prefix="scns-owned-built-")
    token = uuid4().hex[:12]
    network = f"scns-publication-smoke-{token}"
    database = f"scns_built_{token}_e2e_test"
    api, frontend = f"{network}-api", f"{network}-frontend"
    db_id = run(["docker", "compose", "ps", "-q", "db"])
    if not db_id:
        raise RuntimeError("Start the existing Compose db first; no volumes will be deleted.")
    created_db = created_network = connected = False
    containers = []
    try:
        run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "scns",
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f'CREATE DATABASE "{database}"',
            ]
        )
        created_db = True
        run(["docker", "network", "create", network])
        created_network = True
        run(["docker", "network", "connect", "--alias", "db", network, db_id])
        connected = True
        env = {
            **os.environ,
            "DATABASE_URL": f"postgresql+psycopg://scns:scns_local@db:5432/{database}",
            "ALLOWED_ORIGINS": '["http://127.0.0.1:5174"]',
            "APP_ENV": "test",
            "DEMO_ENABLED": "true",
            "LOGIN_IP_LIMIT": "100",
            "SESSION_COOKIE_SECURE": "false",
        }
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                api,
                "--network",
                network,
                "--network-alias",
                "api",
                "--mount",
                f"type=bind,source={private.name},target=/app/storage",
                *[
                    part
                    for key in (
                        "DATABASE_URL",
                        "ALLOWED_ORIGINS",
                        "APP_ENV",
                        "DEMO_ENABLED",
                        "LOGIN_IP_LIMIT",
                        "SESSION_COOKIE_SECURE",
                    )
                    for part in ("-e", key)
                ],
                "scns-api",
            ],
            env,
        )
        containers.append(api)
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                frontend,
                "--network",
                network,
                "-p",
                "127.0.0.1:5174:80",
                "scns-frontend",
            ]
        )
        containers.append(frontend)
        deadline = time.monotonic() + 60
        while True:
            try:
                with urllib.request.urlopen("http://127.0.0.1:5174/admin", timeout=2) as response:
                    assert response.status == 200
                break
            except (OSError, AssertionError):
                if time.monotonic() > deadline:
                    raise RuntimeError("Built nginx did not become ready") from None
                time.sleep(0.25)
        worker_name = f"{network}-worker"
        run(
            [
                "docker",
                "create",
                "--name",
                worker_name,
                "--network",
                network,
                "--mount",
                f"type=bind,source={private.name},target=/app/storage",
                *[
                    part
                    for key in (
                        "DATABASE_URL",
                        "ALLOWED_ORIGINS",
                        "APP_ENV",
                        "DEMO_ENABLED",
                        "LOGIN_IP_LIMIT",
                        "SESSION_COOKIE_SECURE",
                    )
                    for part in ("-e", key)
                ],
                "scns-api",
                "python",
                "-m",
                "app.cli.imports",
                "worker",
            ],
            env,
        )
        containers.append(worker_name)
        test_env = {
            **os.environ,
            "E2E_DATABASE_URL": f"postgresql+psycopg://scns:scns_local@localhost:54329/{database}",
            "SCNS_E2E_BUILT_URL": "http://127.0.0.1:5174",
            "SCNS_E2E_BUILT_WORKER_CONTAINER": worker_name,
            "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH": os.environ.get(
                "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium"
            ),
            "UV_CACHE_DIR": "/tmp/scns-uv-cache",
            "npm_config_cache": "/tmp/scns-npm-cache",
        }
        # Runner resets only this owned *_e2e_test DB, provisions random temporary
        # campus accounts, and runs against built nginx/API (no source webServer).
        result = subprocess.run(
            [
                "uv",
                "run",
                "--frozen",
                "python",
                "-m",
                "tests.browser_runner",
                *(
                    [
                        "educational-indoor.spec.ts",
                        "educational-explorer.spec.ts",
                        "map-explorer.spec.ts",
                        "public-experience.spec.ts",
                        "navigation.spec.ts",
                        "indoor-routing.spec.ts",
                        "admin.spec.ts",
                        "muj-homepage.spec.ts",
                    ]
                    if args.indoor_demo_only
                    else ["muj.spec.ts"]
                    if args.muj_only
                    else [
                        "map-explorer.spec.ts",
                        "map-source-fixture.spec.ts",
                        "preservation-observation.spec.ts",
                        "public-experience.spec.ts",
                        "muj-homepage.spec.ts",
                    ]
                    if args.explorer_only
                    else [
                        "educational-indoor.spec.ts",
                        "educational-explorer.spec.ts",
                        "muj-homepage.spec.ts",
                        "public-experience.spec.ts",
                        "map-explorer.spec.ts",
                        "map-source-fixture.spec.ts",
                        "preservation-observation.spec.ts",
                        "muj.spec.ts",
                        "imports.spec.ts",
                        "admin.spec.ts",
                        "graph.spec.ts",
                        "location.spec.ts",
                        "closures.spec.ts",
                        "qr.spec.ts",
                        "floorplans.spec.ts",
                        "indoor.spec.ts",
                        "indoor-routing.spec.ts",
                        "publication.spec.ts",
                        "navigation.spec.ts",
                    ]
                ),
            ],
            cwd=ROOT / "backend",
            env=test_env,
            check=False,
        )
        if result.returncode:
            return result.returncode
        for path, expected in (
            ("/api/v1/health/ready", 200),
            ("/api/v1/admin/session", 401),
            ("/storage/private-original.geojson", 404),
            ("/data/raw/source.geojson", 404),
        ):
            try:
                with urllib.request.urlopen("http://127.0.0.1:5174" + path, timeout=5) as response:
                    status = response.status
            except urllib.error.HTTPError as error:
                status = error.code
            assert status == expected, "Built app private/readiness boundary failed"
        print(
            "Built MUJ desktop/mobile draft import/map/route/isolation journeys passed."
            if args.muj_only
            else "Built explorer/public-experience journeys passed; private/readiness boundaries verified."
            if args.explorer_only
            else "Built nginx/API/worker floorplan, publication and public-navigation journeys passed; private boundaries verified."
        )
        return 0
    finally:
        # Only this runner's own temporary bind mount, never a retained volume.
        # Root-owned private mode0700 files must be removed by their owning container.
        if api in containers:
            run(
                [
                    "docker",
                    "exec",
                    api,
                    "python",
                    "-c",
                    "from pathlib import Path; import shutil; [(shutil.rmtree(p) if p.is_dir() else p.unlink()) for p in Path('/app/storage').iterdir()]",
                ]
            )
        for container in reversed(containers):
            run(["docker", "rm", "-f", container])
        if connected:
            run(["docker", "network", "disconnect", network, db_id])
        if created_network:
            run(["docker", "network", "rm", network])
        if created_db:
            # Only the uniquely generated disposable database owned by this run.
            assert database.startswith("scns_built_") and database.endswith("_e2e_test")
            run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "db",
                    "psql",
                    "-U",
                    "scns",
                    "-d",
                    "postgres",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    f'DROP DATABASE "{database}" WITH (FORCE)',
                ]
            )
        private.cleanup()
        print(
            "Removed only owned smoke containers/network/disposable DB; development volumes/data preserved."
        )


if __name__ == "__main__":
    sys.exit(main())
