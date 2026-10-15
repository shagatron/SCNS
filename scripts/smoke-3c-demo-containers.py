#!/usr/bin/env python3
"""Built helper workflow; owns only unique test DB/network/containers, no volumes."""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run(args, env=None):
    result = subprocess.run(
        args, cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    if result.returncode:
        # No argv/environment dump: test passwords never cross subprocess boundaries.
        raise RuntimeError(
            f"Owned demo smoke command failed ({args[0]}), exit{result.returncode}: {result.stdout[-6000:]} {result.stderr[-3000:]}"
        )
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--muj",
        action="store_true",
        help="Exercise the MUJ staged helper instead of the synthetic 3C helper",
    )
    args = parser.parse_args()
    private = tempfile.TemporaryDirectory(prefix="scns-owned-muj-")
    token = uuid4().hex[:12]
    network = f"scns-demo-smoke-{token}"
    database = f"scns_demo_{token}_e2e_test"
    db_id = run(["docker", "compose", "ps", "-q", "db"])
    if not db_id:
        raise RuntimeError("Existing Compose db required; no volume changes.")
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
            "APP_ENV": "test",
            "DEMO_ENABLED": "true",
            "LOGIN_IP_LIMIT": "100",
        }
        options = [
            part
            for key in ("DATABASE_URL", "APP_ENV", "DEMO_ENABLED", "LOGIN_IP_LIMIT")
            for part in ("-e", key)
        ]
        api, worker = network + "-api", network + "-worker"
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
                "--mount",
                f"type=bind,source={ROOT / 'backend/tests'},target=/app/backend/tests,readonly",
                *options,
                "scns-api",
            ],
            env,
        )
        containers.append(api)
        run(["docker", "exec", api, "alembic", "upgrade", "head"])
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                worker,
                "--network",
                network,
                "--mount",
                f"type=bind,source={private.name},target=/app/storage",
                *options,
                "scns-api",
                "python",
                "-m",
                "app.cli.imports",
                "worker",
            ],
            env,
        )
        containers.append(worker)
        print(
            run(
                [
                    "docker",
                    "exec",
                    api,
                    "python",
                    "-m",
                    "tests.muj_container" if args.muj else "tests.demo_container",
                ]
            )
        )
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
            assert database.startswith("scns_demo_") and database.endswith("_e2e_test")
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
            "Removed only owned disposable smoke resources; developer volumes/data untouched."
        )


if __name__ == "__main__":
    main()
