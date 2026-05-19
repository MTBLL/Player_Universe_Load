#!/usr/bin/env python3
"""CLI commands for Player Universe Load."""

import os
import subprocess
import sys

from dotenv import load_dotenv

from .__main__ import load_all
from .db import get_connection
from .exporters import PARQUET_DIR, export_all

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


def sync_to_neon():
    """Export local database and upload to Neon."""
    print("\n📦 Exporting local database and uploading to Neon...\n")

    NEON_URL = os.environ.get("NEON_DATABASE_URL")
    if not NEON_URL:
        print("❌ Error: NEON_DATABASE_URL not found in environment or .env")
        print("   Please add NEON_DATABASE_URL=... to .env at the project root")
        sys.exit(1)

    local_url = _local_url()

    # Temporary dump file
    dump_file = "/tmp/fantasy_baseball_dump.sql"

    print("🔄 Step 1: Exporting local database...")
    print(f"   Source: {local_url}")
    print(f"   Output: {dump_file}\n")

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

    print(f"   ✓ Export complete (~{os.path.getsize(dump_file) / 1024 / 1024:.1f}MB)\n")

    print("📤 Step 2: Uploading to Neon...")
    print(
        f"   Target: {NEON_URL.split('@')[1] if '@' in NEON_URL else 'Neon database'}\n"
    )

    # Upload to Neon using psql
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

    print("   ✓ Upload complete\n")

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


def load_and_sync(year: int | None = None):
    """Load to local database, export parquets, then sync to Neon."""
    print("🚀 Full workflow: Load local → Export parquets → Upload to Neon\n")
    print("=" * 60)

    # Step 1: Load locally
    load_local(year=year)

    print("\n" + "=" * 60)

    # Step 2: Export parquets (analytics artifact)
    export_parquets()

    print("\n" + "=" * 60)

    # Step 3: Sync to Neon
    sync_to_neon()

    print("\n" + "=" * 60)
    print("\n✅ Complete! Data loaded locally, exported to parquet, synced to Neon.")


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

  # Verify database
  uv run player-universe-load verify
        """,
    )

    parser.add_argument(
        "command",
        choices=["load-and-sync", "load-local", "sync-to-neon", "export-parquets", "verify"],
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
    elif args.command == "verify":
        verify()

    return 0


if __name__ == "__main__":
    sys.exit(main())
