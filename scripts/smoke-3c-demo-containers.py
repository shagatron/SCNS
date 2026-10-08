#!/usr/bin/env python3
"""Built helper workflow; owns only unique test DB/network/containers, no volumes."""

import os
import subprocess
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
                "--tmpfs",
                "/app/storage",
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
                "--tmpfs",
                "/app/storage",
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
        print(run(["docker", "exec", api, "python", "-m", "tests.demo_container"]))
    finally:
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
        print(
            "Removed only owned disposable smoke resources; developer volumes/data untouched."
        )


if __name__ == "__main__":
    main()
