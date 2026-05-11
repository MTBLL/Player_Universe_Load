#!/usr/bin/env python3
"""CLI commands for Player Universe Load."""

import os
import subprocess
import sys

from dotenv import load_dotenv

from .__main__ import load_all

load_dotenv()


def load_local(year: int | None = None):
    """Load data to local PostgreSQL database."""
    print("🏠 Loading to LOCAL PostgreSQL database...")
    print("   Connection: postgresql://localhost/fantasy_baseball\n")

    # Override to use local database
    os.environ["DATABASE_URL"] = "postgresql://localhost/fantasy_baseball"

    load_all(year=year)


def sync_to_neon():
    """Export local database and upload to Neon."""
    print("\n📦 Exporting local database and uploading to Neon...\n")

    # Read Neon DATABASE_URL directly from .env so a prior local-override
    # in os.environ (set by load_local) doesn't shadow it.
    from dotenv import dotenv_values

    NEON_URL = dotenv_values().get("DATABASE_URL")
    if not NEON_URL:
        print("❌ Error: DATABASE_URL not found in .env")
        print("   Please add DATABASE_URL=... to .env at the project root")
        sys.exit(1)

    # Temporary dump file
    dump_file = "/tmp/fantasy_baseball_dump.sql"

    print("🔄 Step 1: Exporting local database...")
    print("   Source: postgresql://localhost/fantasy_baseball")
    print(f"   Output: {dump_file}\n")

    # Export local database using pg_dump
    pg_dump_result = subprocess.run(
        ["pg_dump", "--clean", "--if-exists", "fantasy_baseball"],
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


def load_and_sync(year: int | None = None):
    """Load to local database and sync to Neon in one command."""
    print("🚀 Full workflow: Load local → Export → Upload to Neon\n")
    print("=" * 60)

    # Step 1: Load locally
    load_local(year=year)

    print("\n" + "=" * 60)

    # Step 2: Sync to Neon
    sync_to_neon()

    print("\n" + "=" * 60)
    print("\n✅ Complete! Data loaded locally and synced to Neon.")


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

  # Verify database
  uv run player-universe-load verify
        """,
    )

    parser.add_argument(
        "command",
        choices=["load-and-sync", "load-local", "sync-to-neon", "verify"],
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
    elif args.command == "verify":
        verify()

    return 0


if __name__ == "__main__":
    sys.exit(main())
