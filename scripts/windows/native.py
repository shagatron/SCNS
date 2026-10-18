"""Native Windows local-only controller; no seed/migrate/publish/reset commands.

All migration writes target a durably reserved NEW DB/storage. Docker access is
backup-only. Exceptions/output are sanitized: no DSNs/passwords/raw PG errors.
"""

import argparse
import base64
import ctypes
import getpass
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import warnings
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.portable import durable_replace, lock_file  # noqa: E402


class SafeError(Exception):
    pass


def acl_diagnostic(stderr):
    """Accept only the ACL helper's bounded, structured diagnostics, never raw stderr."""
    stages = {
        "validate-directory",
        "read-owner",
        "enumerate-profile",
        "build-dacl",
        "persist-dacl",
        "reset-child-dacl",
        "verify-child-dacl",
        "verify-root-dacl",
        "verify-owner",
    }
    for line in stderr.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("SCNS_ACL_ERROR ") or len(line) > 512:
            continue
        try:
            value = json.loads(line.removeprefix("SCNS_ACL_ERROR "))
        except ValueError:
            continue
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("stage"), str)
            or value["stage"] not in stages
        ):
            continue
        code, hresult = value.get("windows_error"), value.get("hresult")
        if code is not None and (type(code) is not int or not 0 <= code <= 65535):
            continue
        if not isinstance(hresult, str) or not re.fullmatch(r"0x[0-9A-Fa-f]{8}", hresult):
            continue
        return f" ACL stage {value['stage']}; Windows error {code}; HRESULT {hresult}."
    return ""


def run(args, *, stdin=None, stdout=subprocess.PIPE, env=None, cwd=ROOT, stage=None):
    result = subprocess.run(
        args, input=stdin, stdout=stdout, stderr=subprocess.PIPE, env=env, cwd=cwd, check=False
    )
    if result.returncode:
        context = f"Native {stage}: " if stage else ""
        detail = acl_diagnostic(result.stderr) if stage else ""
        raise SafeError(
            f"{context}{Path(str(args[0])).name} failed (exit {result.returncode}).{detail} No unsafe automatic retry. Check tool/service availability; credentials and raw output withheld."
        )
    return result.stdout


def protect(path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        raise SafeError(
            "Protected native configuration requires real Windows/DPAPI; Linux is test-only."
        )
    run(
        [
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "RemoteSigned",
            "-File",
            str(ROOT / "scripts/windows/protect.ps1"),
            "-Path",
            str(path),
        ],
        stage="protect-state-directory",
    )


def write(path, value):
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    durable_replace(temp, path)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dpapi(data, *, decrypt=False):
    from ctypes import wintypes as w

    class Blob(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    raw = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, target = Blob(len(data), raw), Blob()
    api = ctypes.WinDLL("crypt32", use_last_error=True)
    fn = api.CryptUnprotectData if decrypt else api.CryptProtectData
    fn.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        w.DWORD,
        ctypes.POINTER(Blob),
    ]
    fn.restype = w.BOOL
    # Current-user scope only. UI forbidden; nothing stored in plaintext.
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise SafeError(
            "Current-user DPAPI refused configuration. Use the original Windows account; preserve the bundle."
        )
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        free = ctypes.WinDLL("kernel32").LocalFree
        free.argtypes, free.restype = [ctypes.c_void_p], ctypes.c_void_p
        free(target.data)


def save_secret(path, value):
    write(
        path, {"dpapi_current_user": base64.b64encode(dpapi(json.dumps(value).encode())).decode()}
    )


def load_secret(path):
    return json.loads(
        dpapi(base64.b64decode(read(path)["dpapi_current_user"], validate=True), decrypt=True)
    )


def password(prompt):
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            return getpass.getpass(prompt)
        except getpass.GetPassWarning:
            raise SafeError("This terminal cannot hide passwords; no echoed fallback.") from None


@contextmanager
def exclusive(state):
    protect(state)
    with (state / "controller.lock").open("a") as handle:
        try:
            lock_file(handle)
        except BlockingIOError:
            raise SafeError(
                "Another native action is running. Stop it normally or wait; do not delete locks."
            ) from None
        yield


def tools(pg_bin=None):
    candidates = [Path(pg_bin)] if pg_bin else []
    if shutil.which("pg_restore"):
        candidates.append(Path(shutil.which("pg_restore")).parent)
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\PostgreSQL\Installations"
            ) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    with winreg.OpenKey(key, winreg.EnumKey(key, index)) as child:
                        candidates.append(
                            Path(winreg.QueryValueEx(child, "Base Directory")[0]) / "bin"
                        )
        except FileNotFoundError:
            pass
    for folder in candidates:
        restore = folder / ("pg_restore.exe" if os.name == "nt" else "pg_restore")
        if restore.is_file() and re.search(rb"\b17\.", run([str(restore), "--version"])):
            return folder
    raise SafeError(
        "PostgreSQL 17 x64 tools not found. Install the official PG17 package; rerun with -PgBin pointing to its actual bin directory."
    )


def pg(folder, name):
    return str(folder / (name + (".exe" if os.name == "nt" else "")))


def file_hashes(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise SafeError(
                "Symlink/junction in private copy; preserve originals and inspect it explicitly."
            )
        if path.is_file():
            h = hashlib.sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            result[path.relative_to(root).as_posix()] = {
                "bytes": path.stat().st_size,
                "sha256": h.hexdigest(),
            }
    return result


def inventory(connection):
    """No record values/password hashes emitted: hash ALL application rows/columns."""
    with connection.cursor() as cur:
        cur.execute("SET LOCAL TIME ZONE 'UTC'")
        cur.execute("SET LOCAL DateStyle = 'ISO, YMD'")
        cur.execute("select current_setting('server_version_num')::int, postgis_lib_version()")
        version, postgis = cur.fetchone()
        cur.execute("select version_num from alembic_version")
        revision = cur.fetchone()[0]
        cur.execute(
            "select tablename from pg_tables where schemaname='public' and tablename <> 'spatial_ref_sys' order by tablename"
        )
        tables = [r[0] for r in cur.fetchall()]
        result = {}
        for table in tables:
            cur.execute(
                sql.SQL(
                    "select row_to_json(t)::text from {} t order by row_to_json(t)::text"
                ).format(sql.Identifier("public", table))
            )
            digests, count = [], 0
            for (row,) in cur:
                data = row.encode("utf-8")
                digests.append(hashlib.sha256(data).digest())
                count += 1
            result[table] = {
                "rows": count,
                "sha256": hashlib.sha256(b"".join(sorted(digests))).hexdigest(),
            }
        cur.execute(
            "select count(*) from pg_constraint where connamespace='public'::regnamespace and not convalidated"
        )
        if cur.fetchone()[0]:
            raise SafeError("Unvalidated source/restored constraints; stop and inspect.")
        cur.execute(
            "select sequencename, last_value from pg_sequences where schemaname='public' order by sequencename"
        )
        sequences = [list(r) for r in cur.fetchall()]
        cur.execute(
            "select a.campus_id::text,a.release_id::text,r.checksum,f.checksum from active_releases a join releases r on r.id=a.release_id left join release_artifacts f on f.release_id=a.release_id order by a.campus_id"
        )
        releases = [list(r) for r in cur.fetchall()]
        return {
            "server_major": version // 10000,
            "postgis": postgis,
            "revision": revision,
            "tables": result,
            "sequences": sequences,
            "active_releases": releases,
        }


def compatible(source, target_major, target_postgis):
    if source["server_major"] != 17 or target_major != 17:
        raise SafeError(
            "Only PostgreSQL 17→17 logical migration is supported; no automatic major upgrade."
        )

    def version(value):
        if not re.fullmatch(r"\d+\.\d+\.\d+", value):
            raise SafeError("Require a stable numeric PostGIS version, not ANY/dev/beta.")
        return tuple(map(int, value.split(".")))

    if not ((3, 5, 0) <= version(source["postgis"]) <= version(target_postgis) < (3, 7, 0)):
        raise SafeError(
            "Require source PostGIS 3.5/3.6 and same-or-newer native 3.5/3.6; inspect available extensions before backup/restore."
        )


def available_postgis(db):
    if os.name == "nt":
        build = db.execute("select version()").fetchone()[0].lower()
        if "visual c++" not in build and "mingw" not in build:
            raise SafeError(
                "Selected server is not recognized as native Windows PostgreSQL. Do not use the Docker/WSL database as the native target."
            )
        addresses = db.execute("show listen_addresses").fetchone()[0]
        if not set(address.strip() for address in addresses.split(",")) <= {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise SafeError(
                "Native PostgreSQL must listen only on loopback. Follow the native-server installation step; no firewall/LAN exception will be added."
            )
    rows = db.execute(
        "select version from pg_available_extension_versions where name='postgis'"
    ).fetchall()
    versions = [row[0] for row in rows if re.fullmatch(r"3\.[56]\.\d+", row[0])]
    if not versions:
        raise SafeError(
            "Install stable PostGIS 3.5 or 3.6 for native PG17 via Stack Builder before migration. No guessed ANY/dev extension version."
        )
    return max(versions, key=lambda value: tuple(map(int, value.split("."))))


def same_data(source, target):
    if any(
        source.get(k) != target.get(k)
        for k in ("revision", "tables", "sequences", "active_releases")
    ):
        raise SafeError(
            "Restored schema/record digests differ. NO native services started; preserve both copies and reports."
        )


COMPOSE = ["docker", "compose", "-f", str(ROOT / "compose.yaml")]


def docker_sql(query):
    # Use actual container PG variables, not assumed host ports/passwords.
    return run(
        [
            *COMPOSE,
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'exec psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
        ],
        stdin=("SET TIME ZONE 'UTC'; SET DateStyle='ISO, YMD';" + query).encode(),
    ).decode("utf-8")


def docker_inventory():
    # Never start API/writers. Hash row content independent of OS text collation.
    metadata = json.loads(
        docker_sql(
            "begin read only; select json_build_object('server_major',current_setting('server_version_num')::int/10000,'postgis',postgis_lib_version(),'revision',(select version_num from alembic_version)); commit;"
        ).strip()
    )
    tables = docker_sql(
        "select tablename from pg_tables where schemaname='public' and tablename <> 'spatial_ref_sys' order by tablename"
    ).splitlines()
    result = {}
    for table in tables:
        if not re.fullmatch("[a-z_][a-z_0-9]*", table):
            raise SafeError("Unexpected table identifier; no guessed SQL.")
        # Encode each row as hex: unambiguous newlines/UTF-8/NULLs; same hash as native.
        rows = docker_sql(
            f"begin read only; select encode(convert_to(row_to_json(t)::text,'UTF8'),'hex') from public.\"{table}\" t order by row_to_json(t)::text; commit;"
        ).splitlines()
        digests = []
        for row in rows:
            data = bytes.fromhex(row)
            digests.append(hashlib.sha256(data).digest())
        result[table] = {
            "rows": len(rows),
            "sha256": hashlib.sha256(b"".join(sorted(digests))).hexdigest(),
        }
    if (
        docker_sql(
            "select count(*) from pg_constraint where connamespace='public'::regnamespace and not convalidated"
        ).strip()
        != "0"
    ):
        raise SafeError("Docker database has unvalidated constraints.")
    sequences = json.loads(
        docker_sql(
            "select coalesce(json_agg(json_build_array(sequencename,last_value) order by sequencename),'[]'::json) from pg_sequences where schemaname='public'"
        ).strip()
    )
    releases = json.loads(
        docker_sql(
            "select coalesce(json_agg(json_build_array(a.campus_id::text,a.release_id::text,r.checksum,f.checksum) order by a.campus_id),'[]'::json) from active_releases a join releases r on r.id=a.release_id left join release_artifacts f on f.release_id=a.release_id"
        ).strip()
    )
    return {**metadata, "tables": result, "sequences": sequences, "active_releases": releases}


def docker_storage_hashes(actual, mount):
    script = 'import pathlib,hashlib,json; r=pathlib.Path("/verify"); p=sorted(r.rglob("*")); assert not any(x.is_symlink() for x in p); print(json.dumps({x.relative_to(r).as_posix():{"bytes":x.stat().st_size,"sha256":hashlib.file_digest(x.open("rb"),"sha256").hexdigest()} for x in p if x.is_file()}))'
    if mount["Type"] not in {"volume", "bind"}:
        raise SafeError("Unsupported private storage mount; no guessed backup.")
    source = mount.get("Name") if mount["Type"] == "volume" else mount["Source"]
    result = run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--mount",
            f"type={mount['Type']},source={source},target=/verify,readonly",
            "--entrypoint",
            "/app/backend/.venv/bin/python",
            actual["Image"],
            "-c",
            script,
        ]
    )
    return json.loads(result)


def check_bundle(bundle):
    report = read(bundle / "manifest.json")
    if report.get("format") != "scns-native-backup-v1" or report.get("complete") is not True:
        raise SafeError(
            "Incomplete/unrecognized backup. Do not restore it; rerun Backup for a new consistent bundle."
        )
    if file_hashes(bundle / "files") != report["files"]:
        raise SafeError("Backup byte/hash verification failed; preserve originals, do not restore.")
    return report


def verify_source_binding(actual):
    from sqlalchemy.engine import make_url

    api_env = dict(value.split("=", 1) for value in actual["Config"]["Env"] if "=" in value)
    if api_env.get("STORAGE_ROOT") != "/app/storage":
        raise SafeError(
            "Actual API storage root is not the supported /app/storage mount. Stop; no guessed private-data backup."
        )
    database_id = run([*COMPOSE, "ps", "-q", "db"]).decode().strip()
    if not database_id:
        raise SafeError("Existing Compose database is not running; no replacement will be created.")
    database = json.loads(run(["docker", "inspect", database_id]))[0]
    db_env = dict(value.split("=", 1) for value in database["Config"]["Env"] if "=" in value)
    url = make_url(api_env.get("DATABASE_URL", ""))
    if (
        url.host != "db"
        or url.port not in {None, 5432}
        or url.database != db_env.get("POSTGRES_DB")
    ):
        raise SafeError(
            "Actual API is not bound to this Compose database. Stop; do not back up a substitute dataset."
        )
    worker_id = run([*COMPOSE, "ps", "--all", "-q", "import-worker"]).decode().strip()
    if worker_id:
        worker = json.loads(run(["docker", "inspect", worker_id]))[0]
        env = dict(value.split("=", 1) for value in worker["Config"]["Env"] if "=" in value)
        other = make_url(env.get("DATABASE_URL", ""))
        if (other.host, other.port or 5432, other.database) != (
            url.host,
            url.port or 5432,
            url.database,
        ) or env.get("STORAGE_ROOT") != "/app/storage":
            raise SafeError(
                "API/worker database or storage roots differ; stop for explicit source reconciliation."
            )

        def mounts(row):
            return {m.get("Source") for m in row["Mounts"] if m["Destination"] == "/app/storage"}

        if mounts(actual) != mounts(worker) or len(mounts(actual)) != 1:
            raise SafeError("API/worker private storage mounts differ; no partial backup.")


def source_inventory(state):
    identity = run([*COMPOSE, "ps", "--all", "-q", "api"]).decode().strip()
    if not identity:
        raise SafeError(
            "Existing API container missing; cannot identify retained private storage. No replacement created."
        )
    actual = json.loads(run(["docker", "inspect", identity]))[0]
    verify_source_binding(actual)
    report = {
        "qualification": "Read-only preliminary inventory while writers may run; Backup repeats after stopping writers for the authoritative snapshot.",
        "database": docker_inventory(),
        "storage_mounts": [
            {k: m.get(k) for k in ("Type", "Name", "Source", "Destination")}
            for m in actual["Mounts"]
            if m["Destination"] == "/app/storage"
        ],
        "api_setting_names": sorted(v.split("=", 1)[0] for v in actual["Config"]["Env"]),
        "root_env_present": (ROOT / ".env").is_file(),
        "git_head": run(["git", "rev-parse", "HEAD"]).decode().strip(),
    }
    write(state / "docker-inventory.json", report)
    print(
        json.dumps(
            {
                "source_database": {k: v for k, v in report["database"].items() if k != "tables"},
                "application_tables": len(report["database"]["tables"]),
                "report": str(state / "docker-inventory.json"),
                "qualification": report["qualification"],
            },
            indent=2,
        )
    )


def backup(state):
    # Compatibility is checked BEFORE stopping writers or taking a backup.
    source_meta = json.loads(
        docker_sql(
            "select json_build_object('server_major',current_setting('server_version_num')::int/10000,'postgis',postgis_lib_version())"
        ).strip()
    )
    admin = admin_connection()
    with psycopg.connect(**admin, autocommit=True) as target:
        major = int(target.execute("show server_version_num").fetchone()[0]) // 10000
        compatible(source_meta, major, available_postgis(target))
    if (
        input("Stops Docker writers; leaves original data intact. Type BACKUP SCNS: ")
        != "BACKUP SCNS"
    ):
        raise SafeError("Not confirmed; no writers stopped.")
    bundle = state / "backups" / str(uuid4())
    protect(bundle)
    write(state / "last-backup.json", {"bundle": str(bundle)})
    write(bundle / "manifest.json", {"format": "scns-native-backup-v1", "complete": False})
    api_id = run([*COMPOSE, "ps", "--all", "-q", "api"]).decode().strip()
    if not api_id:
        raise SafeError(
            "Existing API container/storage reference missing; do not create a replacement."
        )
    actual = json.loads(run(["docker", "inspect", api_id]))[0]
    verify_source_binding(actual)
    mounts = [m for m in actual["Mounts"] if m["Destination"] == "/app/storage"]
    if len(mounts) != 1:
        raise SafeError("Ambiguous private storage mount; inspect the actual container first.")
    original_env = dict(item.split("=", 1) for item in actual["Config"]["Env"] if "=" in item)
    # Save configuration only encrypted; do not copy secrets into manifest/logs.
    save_secret(
        bundle / "configuration.dpapi.json",
        {
            "api_environment": original_env,
            "root_env": base64.b64encode((ROOT / ".env").read_bytes()).decode()
            if (ROOT / ".env").exists()
            else None,
        },
    )
    run([*COMPOSE, "stop", "-t", "45", "frontend", "api", "import-worker"])
    states = json.loads(
        run(
            [
                "docker",
                "inspect",
                *filter(
                    None,
                    [
                        run([*COMPOSE, "ps", "--all", "-q", s]).decode().strip()
                        for s in ("api", "import-worker")
                    ],
                ),
            ]
        )
    )
    if any(r["State"]["Running"] for r in states):
        raise SafeError("A Docker writer is still running; no backup claimed.")
    source = docker_inventory()
    private_before = docker_storage_hashes(actual, mounts[0])
    files = bundle / "files"
    (files / "storage").mkdir(parents=True)
    run(["docker", "cp", f"{api_id}:/app/storage/.", str(files / "storage")])
    for relative in ("storage", "data/raw", "data/staging", "data/exports"):
        if (ROOT / relative).exists():
            shutil.copytree(ROOT / relative, files / "repository" / relative, symlinks=True)
    with (files / "database.dump").open("wb") as dump:
        run(
            [
                *COMPOSE,
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                'exec pg_dump -Fc --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
            ],
            stdout=dump,
        )
    # Validate custom archive directory without restoring or starting a writer.
    with (files / "database.dump").open("rb") as dump:
        process = subprocess.run(
            [*COMPOSE, "exec", "-T", "db", "pg_restore", "--list"],
            stdin=dump,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    if process.returncode:
        raise SafeError(
            "Custom backup archive failed pg_restore --list; no complete backup claimed."
        )
    same_data(source, docker_inventory())
    if private_before != file_hashes(files / "storage") or private_before != docker_storage_hashes(
        actual, mounts[0]
    ):
        raise SafeError(
            "Private Docker storage hashes changed or copy differs. No complete backup claimed."
        )
    report = {
        "format": "scns-native-backup-v1",
        "complete": True,
        "source": source,
        "files": file_hashes(files),
        "source_mount": {k: mounts[0].get(k) for k in ("Type", "Name", "Source", "Destination")},
    }
    write(bundle / "manifest.json", report)
    check_bundle(bundle)
    print(
        f"Verified stopped-writer backup: {bundle}\nDocker writers remain stopped; original database/volume/.env unchanged. Keep this bundle and DPAPI Windows account."
    )


def admin_connection():
    host = input("Native PostgreSQL host [127.0.0.1]: ").strip() or "127.0.0.1"
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise SafeError(
            "Native migration connects only to local loopback; no exposed Windows DB ports."
        )
    port = int(input("Native PostgreSQL port [5432]: ").strip() or "5432")
    user = input("Existing native PostgreSQL administrator [postgres]: ").strip() or "postgres"
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password("Native PostgreSQL admin password (hidden; not saved): "),
        "dbname": "postgres",
        "connect_timeout": 10,
    }


def connection(config):
    return psycopg.connect(**config["database"], connect_timeout=10)


def restore(state, bundle, folder, *, new_target=False):
    report = check_bundle(bundle)
    intent_path = state / "restore-intent.dpapi.json"
    if new_target and intent_path.exists():
        # Preserve the previous reservation/partial copy. Never drop or reuse it.
        shutil.copyfile(intent_path, state / f"previous-restore-{uuid4()}.dpapi.json")
        if (state / "config.dpapi.json").exists():
            shutil.copyfile(
                state / "config.dpapi.json", state / f"previous-config-{uuid4()}.dpapi.json"
            )
    intent = load_secret(intent_path) if intent_path.exists() and not new_target else None
    bundle_hash = hashlib.sha256((bundle / "manifest.json").read_bytes()).hexdigest()
    if intent and (intent["bundle"] != str(bundle) or intent["manifest_sha256"] != bundle_hash):
        raise SafeError(
            "Existing restore intent is bound to another backup. Preserve it; use explicit -NewTarget for a separate new copy."
        )
    admin = admin_connection()
    with psycopg.connect(**admin, autocommit=True) as db:
        target_major = int(db.execute("show server_version_num").fetchone()[0]) // 10000
        target_postgis = available_postgis(db)
        compatible(report["source"], target_major, target_postgis)
        if report["source"]["revision"] != "0016_closures":
            raise SafeError(
                "Backup schema is not the accepted 0016_closures revision. No migration/upgrade will run automatically."
            )
        if (
            not intent
            and not new_target
            and db.execute(
                "select 1 from pg_database where datname ~ '^scns_native_[0-9a-f]{12}$' limit 1"
            ).fetchone()
        ):
            raise SafeError(
                "Existing native copies found but no matching durable intent in this State. Stop and recover the original State; only explicit -NewTarget may authorize a separate additional copy. No automatic duplicate creation."
            )
        if not intent:
            token = uuid4().hex[:12]
            intent = {
                "bundle": str(bundle),
                "manifest_sha256": bundle_hash,
                "dbname": f"scns_native_{token}",
                "user": f"scns_native_{token}",
                "password": secrets.token_urlsafe(36),
                "host": admin["host"],
                "port": admin["port"],
                "postgis": target_postgis,
                "storage": str(state / "copies" / token / "storage"),
                "phase": "reserved",
            }
            save_secret(intent_path, intent)  # durable BEFORE first CREATE
        if (intent["host"], intent["port"]) != (admin["host"], admin["port"]):
            raise SafeError(
                "Restore intent targets a different native server. No automatic retargeting."
            )
        exists = db.execute(
            "select 1 from pg_database where datname=%s", (intent["dbname"],)
        ).fetchone()
        config = {
            "database": {k: intent[k] for k in ("host", "port", "user", "password")},
            "storage": intent["storage"],
            "bundle": str(bundle),
            "manifest_sha256": bundle_hash,
            "pg_bin": str(folder),
        }
        config["database"]["dbname"] = intent["dbname"]
        if exists:
            # A finished/ambiguous restore is reconciled read-only, never replayed.
            try:
                verify_copy(config, report)
            except Exception:
                raise SafeError(
                    "Reserved database already exists but full reconciliation did not pass. No restore replay/drop. Preserve this copy; inspect reports or use Restore -NewTarget to create a different copy."
                ) from None
        else:
            if (
                input(
                    f"Create NEW database {intent['dbname']} and NEW storage only? Type RESTORE SCNS: "
                )
                != "RESTORE SCNS"
            ):
                raise SafeError("Not confirmed; reservation retained, no database created.")
            if db.execute("select 1 from pg_roles where rolname=%s", (intent["user"],)).fetchone():
                raise SafeError(
                    "Reserved role already exists without its database. Creation outcome ambiguous; preserve it and use explicit -NewTarget. No role alteration."
                )
            db.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(intent["user"]),
                    sql.Literal(
                        db.pgconn.encrypt_password(
                            intent["password"].encode(), intent["user"].encode(), b"scram-sha-256"
                        ).decode()
                    ),
                )
            )
            db.execute(
                sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8'").format(
                    sql.Identifier(intent["dbname"]), sql.Identifier(intent["user"])
                )
            )
            db.execute(
                sql.SQL("ALTER DATABASE {} SET timezone TO 'UTC'").format(
                    sql.Identifier(intent["dbname"])
                )
            )
            intent["phase"] = "database-created"
            save_secret(intent_path, intent)
            with psycopg.connect(
                **{**admin, "dbname": intent["dbname"]}, autocommit=True
            ) as target:
                target.execute(
                    sql.SQL("CREATE EXTENSION postgis VERSION {}").format(
                        sql.Literal(intent["postgis"])
                    )
                )
            env = {
                **os.environ,
                "PGHOST": admin["host"],
                "PGPORT": str(admin["port"]),
                "PGUSER": admin["user"],
                "PGPASSWORD": admin["password"],
                "PGDATABASE": intent["dbname"],
            }
            run(
                [
                    pg(folder, "pg_restore"),
                    "--exit-on-error",
                    "--single-transaction",
                    "--no-owner",
                    "--no-acl",
                    "--dbname",
                    intent["dbname"],
                    str(bundle / "files/database.dump"),
                ],
                env=env,
            )
            env.pop("PGPASSWORD", None)
            # Extension objects remain owned by the native PG administrator.
            # Restoring as the restricted app role cannot COMMENT ON EXTENSION.
            # Grant normal application DML explicitly, never elevate the app role.
            with psycopg.connect(
                **{**admin, "dbname": intent["dbname"]}, autocommit=True
            ) as target:
                target.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(intent["user"])
                    )
                )
                for table in report["source"]["tables"]:
                    privileges = (
                        sql.SQL("SELECT")
                        if table == "alembic_version"
                        else sql.SQL("SELECT, INSERT, UPDATE, DELETE")
                    )
                    target.execute(
                        sql.SQL("GRANT {} ON TABLE {} TO {}").format(
                            privileges,
                            sql.Identifier("public", table),
                            sql.Identifier(intent["user"]),
                        )
                    )
                target.execute(
                    sql.SQL("GRANT SELECT ON TABLE public.spatial_ref_sys TO {}").format(
                        sql.Identifier(intent["user"])
                    )
                )
                target.execute(
                    sql.SQL(
                        "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {}"
                    ).format(sql.Identifier(intent["user"]))
                )
            protect(Path(intent["storage"]).parent)
            # Restore to a unique fresh path; never merge into original/local storage.
            shutil.copytree(bundle / "files/storage", intent["storage"])
            repo_copy = bundle / "files/repository"
            if repo_copy.exists():
                shutil.copytree(repo_copy, Path(intent["storage"]).parent / "repository")
            verify_copy(config, report)
        source_env = load_secret(bundle / "configuration.dpapi.json")["api_environment"]
        # Only application settings, never container PATH/runtime/DB/storage bindings.
        from app.core.config import Settings

        setting_names = {key.upper() for key in Settings.model_fields} - {
            "DATABASE_URL",
            "STORAGE_ROOT",
            "ALLOWED_ORIGINS",
            "PUBLIC_APP_URL",
            "APP_ENV",
        }
        config["settings"] = {
            key: value for key, value in source_env.items() if key in setting_names
        }
        save_secret(state / "config.dpapi.json", config)
        intent["phase"] = "verified"
        save_secret(intent_path, intent)
        write(
            state / "verified-copy.json",
            {
                "database": intent["dbname"],
                "storage": intent["storage"],
                "bundle": str(bundle),
                "manifest_sha256": bundle_hash,
                "schema": report["source"]["revision"],
                "tables": report["source"]["tables"],
            },
        )
        print(
            f"Native copy verified: {intent['dbname']}\nStorage: {intent['storage']}\nDocker original untouched/stopped. No service started, no schema upgrade or publication."
        )


def verify_copy(config, report):
    with connection(config) as db:
        db.execute("SET TRANSACTION READ ONLY")
        actual = inventory(db)
        same_data(report["source"], actual)
        # Every active staged-upload reference must retain its original private bytes.
        for key, state in db.execute("select storage_key,state from import_jobs"):
            if (
                state not in {"committed", "cancelled"}
                and not (Path(config["storage"]) / "private/imports" / key).is_file()
            ):
                raise SafeError(
                    "Active import references a missing private file. No native worker may run."
                )
    if file_hashes(Path(config["storage"])) != {
        name.removeprefix("storage/"): value
        for name, value in report["files"].items()
        if name.startswith("storage/")
    }:
        raise SafeError("Restored private storage hashes differ. No native service started.")
    repo = Path(config["storage"]).parent / "repository"
    if file_hashes(repo) != {
        name.removeprefix("repository/"): value
        for name, value in report["files"].items()
        if name.startswith("repository/")
    }:
        raise SafeError("Restored helper journals/receipt/source copies differ.")


def environment(config, state):
    from sqlalchemy.engine import URL

    d = config["database"]
    # Exclude .env entirely; source explicit application limits retained encrypted.
    env = {
        **os.environ,
        **config.get("settings", {}),
        "SCNS_ENV_FILE": str(state / "unused-do-not-create.env"),
        "DATABASE_URL": URL.create(
            "postgresql+psycopg",
            username=d["user"],
            password=d["password"],
            host=d["host"],
            port=d["port"],
            database=d["dbname"],
        ).render_as_string(hide_password=False),
        "STORAGE_ROOT": config["storage"],
        "APP_ENV": "development",
        "PUBLIC_APP_URL": "http://localhost:5173",
        "ALLOWED_ORIGINS": '["http://localhost:5173","http://127.0.0.1:5173"]',
        "API_PROXY_TARGET": "http://127.0.0.1:8000",
        "PYTHONUTF8": "1",
    }
    return env


def setup_decoder():
    from app.core.windows_sandbox import free_sid, profile_folder, profile_sid, sid_text

    sid = profile_sid()
    try:
        value = sid_text(sid)
        # Read/execute runtime files only, never the repo root/.env/storage/native state.
        for path in {Path(sys.base_prefix), ROOT / "backend/.venv", ROOT / "backend/app"}:
            run(
                ["icacls", str(path), "/grant", f"*{value}:(OI)(CI)(RX)", "/T", "/Q"],
                stage="grant-decoder-runtime-read",
            )
        run(
            [
                "pwsh",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "RemoteSigned",
                "-File",
                str(ROOT / "scripts/windows/protect.ps1"),
                "-Path",
                str(profile_folder()),
                "-ReadOnlySid",
                value,
                "-Recurse",
            ],
            stage="protect-decoder-profile",
        )
    finally:
        free_sid(sid)
    print(
        "Decoder profile configured with read-only runtime access; no network capabilities granted. Actual probe is mandatory before startup."
    )


def decoder_check():
    import io

    from PIL import Image
    from pypdf import PdfWriter

    from app.core.windows_sandbox import run_decoder
    from app.services.floorplans import decode

    # Fail if actual file/network/token/job isolation cannot be established.
    result = json.loads(run_decoder(b"", probe=True))
    if result != {
        "filesystem_denied": True,
        "network_denied": True,
        "database_env_absent": True,
        "filesystem_write_denied": True,
    }:
        raise SafeError(
            "Native decoder isolation probe failed. Do not start processing or bypass AppContainer."
        )
    image = io.BytesIO()
    Image.new("RGB", (80, 60), "red").save(image, format="PNG")
    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(pdf)
    for raw, name in [(image.getvalue(), "probe.png"), (pdf.getvalue(), "probe.pdf")]:
        png, metadata = decode(raw, {"filename": name, "page": 1, "redactions": []})
        with Image.open(io.BytesIO(png)) as rendered:
            rendered.load()
            if rendered.format != "PNG" or not metadata["width_px"]:
                raise SafeError("Actual native PDF/image processing failed.")
    print("Actual native AppContainer/job/file/network probe and PDF+PNG decoding passed.")


def versions(folder):
    if sys.version_info[:2] not in {(3, 12), (3, 13)} or platform.machine().lower() not in {
        "amd64",
        "x86_64",
    }:
        raise SafeError("Require Python 3.12/3.13 x64; ARM/32-bit native runtime is not validated.")
    version = run(["node", "--version"]).decode().strip()
    parts = tuple(map(int, version.lstrip("v").split(".")[:2]))
    if not ((22, 12) <= parts < (23, 0) or (24, 0) <= parts < (25, 0)):
        raise SafeError(
            "Use supported Node 22.12+ or 24 LTS x64; frozen npm dependencies required."
        )
    print(
        "Python:",
        platform.python_version(),
        "; Node:",
        version,
        "; PostgreSQL tools:",
        run([pg(folder, "pg_restore"), "--version"]).decode().strip(),
    )


def start(state, config):
    from app.core.windows_sandbox import Job

    env = environment(config, state)
    # Deliberately verify connectivity/schema BEFORE starting any API/worker.
    try:
        with connection(config) as db:
            available_postgis(db)
            if (
                db.execute("select version_num from alembic_version").fetchone()[0]
                != "0016_closures"
            ):
                raise SafeError("Native database schema mismatch; no automatic migration/seed.")
    except psycopg.OperationalError:
        raise SafeError(
            "Native PostgreSQL is not ready. Check the registered PG17 Windows service and saved local port; do not start Docker as a database substitute or run a seed/reset."
        ) from None
    decoder_check()
    for port in (8000, 5173):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                raise SafeError(
                    f"Loopback port {port} is busy. Stop Docker/native app normally; do not kill an unknown process."
                ) from None
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SafeError("Compiled frontend missing; run Setup first.")
    processes, logs = [], []
    job = Job()
    (state / "stop.request").unlink(missing_ok=True)

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, interrupt)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, interrupt)
    commands = [
        (
            "api",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
            ],
        ),
        (
            "frontend",
            [
                shutil.which("node"),
                str(ROOT / "node_modules/vite/bin/vite.js"),
                "preview",
                "--config",
                str(ROOT / "frontend/vite.native.config.mjs"),
                "--host",
                "127.0.0.1",
                "--port",
                "5173",
                "--strictPort",
            ],
        ),
        ("worker", [sys.executable, "-m", "app.cli.imports", "worker"]),
    ]
    try:
        for name, args in commands:
            # Timestamped protected log; never command/environment/password dumps.
            log = (state / f"{name}-{time.time_ns()}.log").open("ab", buffering=0)
            logs.append(log)
            process = job.spawn(
                args,
                cwd=ROOT / ("frontend" if name == "frontend" else "backend"),
                env=(
                    env
                    if name != "frontend"
                    else {
                        **{
                            key: value
                            for key, value in os.environ.items()
                            if key.upper()
                            in {
                                "SYSTEMROOT",
                                "WINDIR",
                                "PATH",
                                "PATHEXT",
                                "COMSPEC",
                                "TEMP",
                                "TMP",
                                "USERPROFILE",
                                "APPDATA",
                                "LOCALAPPDATA",
                            }
                        },
                        "API_PROXY_TARGET": "http://127.0.0.1:8000",
                    }
                ),
                stdout=log,
            )
            processes.append(process)
            if name == "api":
                ready("http://127.0.0.1:8000/api/v1/health/ready", process)
            if name == "frontend":
                ready("http://localhost:5173/api/v1/health/ready", process)
        write(
            state / "running.json",
            {
                "supervisor": os.getpid(),
                "started": time.time(),
                "database": config["database"]["dbname"],
                "logs": [str(f.name) for f in logs],
            },
        )
        print(
            f"Native app ready: http://localhost:5173/\nProtected logs: {state}\nKeep this terminal open. Ctrl+C or scns.ps1 Stop shuts down only this process tree. Closing/rebooting kills the Job Object tree; restart with Start, never Setup/Restore."
        )
        while all(p.poll() is None for p in processes) and not (state / "stop.request").exists():
            time.sleep(0.25)
        if any(p.poll() is not None for p in processes):
            raise SafeError(
                "A native child exited; all owned services stopped. Inspect protected logs; durable jobs recover on next Start."
            )
    except KeyboardInterrupt:
        pass
    finally:
        # Stop worker first, then frontend/API. PG transactions roll back on forced exit.
        for process in reversed(processes):
            if process.poll() is None:
                try:
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                except OSError:
                    pass
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and any(p.poll() is None for p in processes):
            time.sleep(0.1)
        job.close()
        for process in processes:
            process.wait(timeout=10)
            process.close()
        for log in logs:
            log.close()
        (state / "running.json").unlink(missing_ok=True)
        (state / "stop.request").unlink(missing_ok=True)
        print(
            "Owned native API/frontend/worker stopped; PostgreSQL service and both data copies retained."
        )


def ready(url, process):
    for _ in range(80):
        if process.poll() is not None:
            raise SafeError("Service exited before readiness; inspect protected logs.")
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200 and json.load(r).get("database") == "ready":
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    raise SafeError(
        "Readiness timeout; existing DB must be running. No seed/migration/reset attempted."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "setup",
            "preflight",
            "inventory",
            "backup",
            "restore",
            "start",
            "stop",
            "verify",
            "test",
        ],
    )
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--pg-bin", type=Path)
    parser.add_argument("--new-target", action="store_true")
    args = parser.parse_args()
    state = args.state.resolve()
    if len(state.parts) < 4 or state.is_relative_to(ROOT) or state in ROOT.parents:
        raise SafeError(
            "Use a dedicated native state subdirectory OUTSIDE the repository, never a drive/user root."
        )
    marker = state / "native-state-v1.json"
    if marker.exists() and read(marker).get("format") != "scns-native-state-v1":
        raise SafeError("Existing state marker is unrecognized; no ACL/config changes.")
    if state.exists() and not marker.exists() and any(state.iterdir()):
        raise SafeError(
            "Existing non-native directory selected as state. No ACL/config changes; select an empty dedicated directory."
        )
    for runtime in (
        Path(sys.base_prefix).resolve(),
        (ROOT / "backend/.venv").resolve(),
        (ROOT / "backend/app").resolve(),
    ):
        if state.is_relative_to(runtime):
            raise SafeError("Native state must be outside decoder-readable runtime directories.")
    if os.name != "nt":
        raise SafeError(
            "Native commands must run in Windows PowerShell. Linux can run isolated unit/integration tests, not migrate your Windows database."
        )
    protect(state)
    if not marker.exists():
        write(marker, {"format": "scns-native-state-v1"})
    # Controller imports may construct an ORM engine, but must NEVER fall back
    # to the original Docker .env/database. Real native/test children receive an
    # explicit copied/test URL; source reads use only the explicit Docker API.
    os.environ.update(
        SCNS_ENV_FILE=str(state / "unused-do-not-create.env"),
        DATABASE_URL="postgresql+psycopg://native_helper@127.0.0.1:1/native_helper_no_runtime_database",
        STORAGE_ROOT=str(state / "helper-scratch"),
    )
    for name in (
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGPASSFILE",
        "PGOPTIONS",
    ):
        os.environ.pop(name, None)
    if args.action == "stop":
        if not (state / "running.json").exists():
            print("No recorded native supervisor. No PID killed or database changed.")
            return
        write(state / "stop.request", {"requested": time.time()})
        print(
            "Stop requested. Wait for the Start terminal to report all owned services stopped; no PID reuse risk."
        )
        return
    with exclusive(state):
        folder = tools(args.pg_bin)
        versions(folder)
        if args.action == "setup":
            setup_decoder()
            decoder_check()
        elif args.action == "preflight":
            decoder_check()
            print(
                "Native toolchain/decoder preflight passed; database copy and Windows acceptance are separate."
            )
        elif args.action == "backup":
            backup(state)
        elif args.action == "inventory":
            source_inventory(state)
        elif args.action == "restore":
            bundle = args.bundle or Path(read(state / "last-backup.json")["bundle"])
            restore(state, bundle.resolve(), folder, new_target=args.new_target)
        elif args.action == "start":
            start(state, load_secret(state / "config.dpapi.json"))
        elif args.action == "verify":
            config = load_secret(state / "config.dpapi.json")
            report = check_bundle(Path(config["bundle"]))
            verify_copy(config, report)
            decoder_check()
            print(
                "Full initial DB/storage/journal reconciliation passed. Run before the first Start; legitimate subsequent edits change digests, not a reason to restore again."
            )
        elif args.action == "test":
            decoder_check()
            isolated_tests(state)


def isolated_tests(state):
    """Own only newly created nonce-named DBs; no fallback developer/test URL."""
    from sqlalchemy.engine import URL

    from app.core.windows_sandbox import Job

    if (
        input("Create fresh disposable verification databases only? Type TEST ISOLATED: ")
        != "TEST ISOLATED"
    ):
        raise SafeError("Not confirmed; no test database created.")
    admin = admin_connection()
    token = uuid4().hex[:12]
    names = [f"scns_native_{token}{suffix}" for suffix in ("_test", "_e2e_test", "_migration_test")]
    directory = state / "tests" / token
    protect(directory)
    created = []
    job = Job()
    try:
        with psycopg.connect(**admin, autocommit=True) as db:
            for name in names:
                db.execute(
                    sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name))
                )
                created.append(name)
                with psycopg.connect(**{**admin, "dbname": name}, autocommit=True) as test:
                    test.execute("CREATE EXTENSION postgis")

        def url(name):
            return URL.create(
                "postgresql+psycopg",
                username=admin["user"],
                password=admin["password"],
                host=admin["host"],
                port=admin["port"],
                database=name,
            ).render_as_string(hide_password=False)

        env = {
            **os.environ,
            "SCNS_ENV_FILE": str(directory / "unused.env"),
            "APP_ENV": "test",
            "DEMO_ENABLED": "true",
            "DATABASE_URL": url(names[0]),
            "TEST_DATABASE_URL": url(names[0]),
            "E2E_DATABASE_URL": url(names[1]),
            "MIGRATION_DATABASE_URL": url(names[2]),
            "STORAGE_ROOT": str(directory / "storage"),
            "API_PROXY_TARGET": "http://127.0.0.1:8001",
        }
        commands = [
            [shutil.which("node"), "--test", str(ROOT / "scripts/windows/preview.test.mjs")],
            [sys.executable, "-m", "pytest", "-q", "tests/unit", "tests/integration"],
            [sys.executable, "-m", "tests.migration_runner"],
            [
                sys.executable,
                "-m",
                "tests.browser_runner",
                "navigation.spec.ts",
                "public-experience.spec.ts",
                "muj-homepage.spec.ts",
                "location.spec.ts",
                "qr.spec.ts",
                "closures.spec.ts",
                "indoor-routing.spec.ts",
                "admin.spec.ts",
                "imports.spec.ts",
                "floorplans.spec.ts",
            ],
        ]
        for index, command in enumerate(commands, 1):
            with (directory / f"check-{index}.log").open("wb") as log:
                child = job.spawn(
                    command,
                    cwd=ROOT / "backend",
                    env=env,
                    stdout=log,
                )
                result = child.wait()
                child.close()
                if result:
                    raise SafeError(
                        f"Isolated native check {index} failed; inspect protected check-{index}.log. Retained databases not used."
                    )
        write(
            directory / "passed.json",
            {
                "databases": names,
                "checks": len(commands),
                "qualification": "Actual native run, isolated fixtures only; retained Windows MUJ acceptance remains separate.",
            },
        )
        print(f"Isolated native checks passed. Protected logs: {directory}")
    finally:
        job.close()
        with psycopg.connect(**admin, autocommit=True) as db:
            for name in created:
                if not name.startswith(f"scns_native_{token}") or not name.endswith("_test"):
                    raise SafeError("Refusing unexpected cleanup target.")
                db.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    try:
        main()
    except (SafeError, KeyboardInterrupt) as error:
        print(
            str(error) or "Interrupted; preserve intent/backups and both copies.", file=sys.stderr
        )
        sys.exit(1)
    except Exception as error:
        # DB drivers may include DSNs/query literals. Never dump exception details.
        print(
            f"Native action stopped ({type(error).__name__}, Windows error {getattr(error, 'winerror', None)}); credentials/raw exception withheld. Preserve files and consult recovery steps.",
            file=sys.stderr,
        )
        sys.exit(1)
