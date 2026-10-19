"""One bounded DB worker; no Redis or external service. See docs/operations/imports.md."""

import argparse
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import engine
from app.models.imports import ImportJob
from app.schemas.imports import ImportOptions
from app.services.imports import (
    parse_content,
    private_path,
    process_job,
    storage_dir,
    strict_json,
    transition,
)


def once():
    from app.services.floorplans import once as floorplan_once

    floorplan_work = floorplan_once(engine)
    with Session(engine.execution_options(isolation_level="READ COMMITTED")) as db, db.begin():
        job = db.scalar(
            select(ImportJob)
            .where(
                or_(
                    ImportJob.state == "uploaded",
                    (ImportJob.state == "parsing")
                    & (ImportJob.updated_at < datetime.now(UTC) - timedelta(seconds=180)),
                )
            )
            .order_by(ImportJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return floorplan_work
        if job.attempts >= 3:
            transition(job, "failed")
            job.failure = "Worker recovery exhausted three attempts. Inspect the file and resubmit a corrected batch."
            return True
        job.attempts += 1
        transition(job, "parsing")
        identity = job.id
    with Session(engine.execution_options(isolation_level="READ COMMITTED")) as db, db.begin():
        job = db.scalar(select(ImportJob).where(ImportJob.id == identity).with_for_update())
        if job.state == "parsing":
            process_job(db, job)
    return True


def cleanup(days):
    cutoff = datetime.now(UTC) - timedelta(days=days)
    with Session(engine) as db, db.begin():
        jobs = list(db.scalars(select(ImportJob)))
        registered = {job.storage_key for job in jobs}
        removed = 0
        for job in jobs:
            # Keep DB history/preview/audits. Never delete an active or retryable upload.
            if job.state in {"committed", "cancelled"} and job.updated_at < cutoff:
                path = private_path(job)
                removed += path.exists()
                path.unlink(missing_ok=True)
        for path in storage_dir().glob("*.upload"):
            if path.name not in registered and path.stat().st_mtime < cutoff.timestamp():
                path.unlink()
                removed += 1
        print(f"Removed {removed} expired private/orphan uploads; retained job history.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["worker", "once", "cleanup", "validate"])
    parser.add_argument("--file", type=Path)
    parser.add_argument("--options", type=Path)
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()
    if args.command == "once":
        once()
    elif args.command == "worker":
        # Each child has a hard wall timeout. A killed worker's durable lease is recoverable.
        while True:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "app.cli.imports", "once"],
                    timeout=get_settings().import_parse_seconds + 60,
                    check=False,
                )
                if result.returncode:
                    print(
                        "Import worker failed; durable lease will recover (bounded to three attempts).",
                        file=sys.stderr,
                    )
            except subprocess.TimeoutExpired:
                print("Import processing timeout; durable lease will recover.", file=sys.stderr)
            time.sleep(1)
    elif args.command == "cleanup":
        if args.retention_days < 1:
            parser.error("Retention must be at least one day")
        cleanup(args.retention_days)
    else:
        if not args.file or not args.options:
            parser.error("validate requires --file and --options")
        if args.file.stat().st_size > get_settings().import_byte_limit:
            parser.error("File exceeds upload byte limit")
        options = ImportOptions.model_validate(strict_json(args.options.read_text()))
        rows = parse_content(
            args.file.read_bytes(),
            options,
            SimpleNamespace(code=options.campus_code, timezone=options.timezone),
        )
        print(
            f"Parsed {len(rows)} rows; database references/geometry/conflicts require an authorized staged preview. No database writes performed."
        )


if __name__ == "__main__":
    main()
