#!/usr/bin/env python3
"""CLI commands for Player Universe Load."""

import os
import subprocess
import sys

from dotenv import load_dotenv

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .__main__ import load_all
from .db import console, get_connection
from .exporters import PARQUET_DIR, export_all, upload_all, verify_all

load_dotenv()

DEFAULT_LOCAL_URL = "postgresql://localhost/fantasy_baseball"


def _local_url() -> str:
    return os.environ.get("LOCAL_DATABASE_URL", DEFAULT_LOCAL_URL)


def load_local(year: int | None = None):
    """Load data to local PostgreSQL database."""
    local_url = _local_url()
    print("🏠 Loading to LOCAL PostgreSQL database...")
    print(f"   Connection: {local_url}\n")

    os.environ["DATABASE_URL"] = local_url
    load_all(year=year)


def _spinner_progress(description: str) -> Progress:
    """Indeterminate spinner + elapsed-time bar.

    Rich runs its live display on an internal thread, so the spinner keeps
    ticking while the main thread blocks inside subprocess.run / wait.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn(f"[bold]{description}"),
        BarColumn(bar_width=30),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


def sync_to_neon():
    """Export local database and upload to Neon."""
    print("\n📦 Exporting local database and uploading to Neon...\n")

    NEON_URL = os.environ.get("NEON_DATABASE_URL")
    if not NEON_URL:
        print("❌ Error: NEON_DATABASE_URL not found in environment or .env")
        print("   Please add NEON_DATABASE_URL=... to .env at the project root")
        sys.exit(1)

    local_url = _local_url()
    dump_file = "/tmp/fantasy_baseball_dump.sql"

    # --- Step 1: pg_dump ---
    print("🔄 Step 1: Exporting local database...")
    print(f"   Source: {local_url}")
    print(f"   Output: {dump_file}\n")

    with _spinner_progress("🔄 pg_dump (Postgres → SQL)") as progress:
        progress.add_task("dump", total=None)
        # pg_dump accepts a connection URI as its positional dbname argument,
        # which lets this work against both a local socket and a containerized
        # postgres reachable via host:port.
        pg_dump_result = subprocess.run(
            ["pg_dump", "--clean", "--if-exists", local_url],
            stdout=open(dump_file, "w"),
            stderr=subprocess.PIPE,
            text=True,
        )

    if pg_dump_result.returncode != 0:
        print(f"❌ pg_dump failed: {pg_dump_result.stderr}")
        sys.exit(1)

    dump_mb = os.path.getsize(dump_file) / 1024 / 1024
    console.print(f"   [green]✓[/green] Export complete ([bold]{dump_mb:.1f}MB[/bold])\n")

    # --- Step 2: psql upload to Neon ---
    target_label = NEON_URL.split('@')[1] if '@' in NEON_URL else 'Neon database'
    print("📤 Step 2: Uploading to Neon...")
    print(f"   Target: {target_label}\n")

    with _spinner_progress(f"📤 psql restore → {target_label}") as progress:
        progress.add_task("psql", total=None)
        psql_result = subprocess.run(
            ["psql", NEON_URL],
            stdin=open(dump_file, "r"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    if psql_result.returncode != 0:
        print(f"❌ psql upload failed: {psql_result.stderr}")
        sys.exit(1)

    console.print("   [green]✓[/green] Upload complete\n")

    # Cleanup
    print("🧹 Cleaning up...")
    os.remove(dump_file)
    print(f"   ✓ Removed {dump_file}\n")

    print("✅ Sync to Neon complete!")


def export_parquets():
    """Export local Postgres tables to parquet files under PARQUET_DIR."""
    print("📦 Exporting Postgres tables to parquet files...")
    print(f"   Target dir: {PARQUET_DIR}\n")

    os.environ["DATABASE_URL"] = _local_url()
    conn = get_connection()
    try:
        paths = export_all(conn)
    finally:
        conn.close()

    print(f"\n✅ Exported {len(paths)} parquet files to {PARQUET_DIR}")


def upload_parquets():
    """Upload local parquet files to R2 and record metadata in Postgres."""
    print("☁️  Uploading parquet files to R2...")
    print(f"   Source dir: {PARQUET_DIR}\n")

    os.environ["DATABASE_URL"] = _local_url()
    conn = get_connection()
    try:
        results = upload_all(conn)
    finally:
        conn.close()

    total_bytes = sum(r["size_bytes"] for r in results)
    print(
        f"\n✅ Uploaded {len(results)} parquet files "
        f"({total_bytes / 1024 / 1024:.1f}MB) to R2"
    )


def parquet_and_sync():
    """Parquet pipeline: export local Postgres -> parquet -> upload to R2.

    Mirrors load-and-sync's shape for just the parquet path. Useful when
    the local Postgres is already current and you want to refresh R2
    without re-running the full ETL.
    """
    print("📦 Parquet workflow: Export parquets → Upload to R2\n")
    print("=" * 60)
    export_parquets()
    print("\n" + "=" * 60)
    upload_parquets()
    print("\n" + "=" * 60)
    print("\n✅ Complete! Parquets exported and uploaded to R2.")


def verify_r2():
    """Verify each R2 object matches its parquet_artifacts row.

    Downloads each object, checks the PAR1 magic, recomputes sha256, and
    compares against the recorded value. Exits non-zero if any mismatch.
    """
    print("🔍 Verifying R2 objects against parquet_artifacts metadata...\n")

    os.environ["DATABASE_URL"] = _local_url()
    conn = get_connection()
    try:
        results = verify_all(conn)
    finally:
        conn.close()

    ok = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"]]
    for r in results:
        flag = "✓" if r["ok"] else "✗"
        if r["ok"]:
            print(f"  {flag} {r['table']:<32} {r['size_bytes']:>10,} bytes")
        else:
            print(f"  {flag} {r['table']:<32} {r['error']}")
    print(f"\nResult: {len(ok)} ok, {len(bad)} failed")
    if bad:
        sys.exit(1)
    print("\n✅ All R2 objects verified.")


def load_and_sync(year: int | None = None):
    """Load local -> export parquets -> upload parquets to R2 -> sync to Neon."""
    print(
        "🚀 Full workflow: Load local → Export parquets → Upload to R2 → Upload to Neon\n"
    )
    print("=" * 60)

    # Step 1: Load locally
    load_local(year=year)

    print("\n" + "=" * 60)

    # Step 2: Export parquets (local files)
    export_parquets()

    print("\n" + "=" * 60)

    # Step 3: Upload parquets to R2 (records metadata in local Postgres
    # *before* the dump, so the parquet_artifacts table travels to Neon).
    upload_parquets()

    print("\n" + "=" * 60)

    # Step 4: Sync local Postgres to Neon (carries parquet_artifacts metadata)
    sync_to_neon()

    print("\n" + "=" * 60)
    print(
        "\n✅ Complete! Data loaded locally, parquets exported + uploaded to R2, "
        "synced to Neon."
    )


def verify():
    """Verify database tables and data."""
    from .verification import verify_database

    verify_database()


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Player Universe Database Loader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load locally and sync to Neon (full workflow)
  uv run player-universe-load load-and-sync

  # Just load locally (fast testing)
  uv run player-universe-load load-local

  # Just sync to Neon (if local DB already loaded)
  uv run player-universe-load sync-to-neon

  # Just export parquets from current local DB
  uv run player-universe-load export-parquets

  # Just upload existing parquets to R2 + record metadata
  uv run player-universe-load upload-parquets

  # Parquet pipeline (export + upload) without touching the database load
  uv run player-universe-load parquet-and-sync

  # Verify R2 objects against the parquet_artifacts metadata (sha256 + PAR1)
  uv run player-universe-load verify-r2

  # Verify database structure and counts
  uv run player-universe-load verify
        """,
    )

    parser.add_argument(
        "command",
        choices=[
            "load-and-sync",
            "load-local",
            "sync-to-neon",
            "export-parquets",
            "upload-parquets",
            "parquet-and-sync",
            "verify-r2",
            "verify",
        ],
        help="Command to execute",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Season year to stamp on loaded rows (default: current year)",
    )

    args = parser.parse_args()

    if args.command == "load-and-sync":
        load_and_sync(year=args.year)
    elif args.command == "load-local":
        load_local(year=args.year)
    elif args.command == "sync-to-neon":
        sync_to_neon()
    elif args.command == "export-parquets":
        export_parquets()
    elif args.command == "upload-parquets":
        upload_parquets()
    elif args.command == "parquet-and-sync":
        parquet_and_sync()
    elif args.command == "verify-r2":
        verify_r2()
    elif args.command == "verify":
        verify()

    return 0


if __name__ == "__main__":
    sys.exit(main())
