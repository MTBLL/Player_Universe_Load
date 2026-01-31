#!/usr/bin/env python3
"""CLI commands for Player Universe Load."""

import os
import sys
import subprocess
from pathlib import Path

from .db import get_connection
from .__main__ import load_all


def load_local():
    """Load data to local PostgreSQL database."""
    print("🏠 Loading to LOCAL PostgreSQL database...")
    print("   Connection: postgresql://localhost/fantasy_baseball\n")

    # Override to use local database
    os.environ['DATABASE_URL'] = 'postgresql://localhost/fantasy_baseball'

    load_all()


def sync_to_neon():
    """Export local database and upload to Neon."""
    print("\n📦 Exporting local database and uploading to Neon...\n")

    # Find the export script
    script_path = Path(__file__).parent.parent / "scripts" / "export_and_upload.sh"

    if not script_path.exists():
        print(f"❌ Error: Export script not found at {script_path}")
        sys.exit(1)

    # Run the shell script
    result = subprocess.run(["bash", str(script_path)])

    if result.returncode != 0:
        print("\n❌ Upload to Neon failed!")
        sys.exit(1)


def load_and_sync():
    """Load to local database and sync to Neon in one command."""
    print("🚀 Full workflow: Load local → Export → Upload to Neon\n")
    print("=" * 60)

    # Step 1: Load locally
    load_local()

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
  uv run -m player_universe_load load-and-sync

  # Just load locally (fast testing)
  uv run -m player_universe_load load-local

  # Just sync to Neon (if local DB already loaded)
  uv run -m player_universe_load sync-to-neon

  # Verify database
  uv run -m player_universe_load verify
        """
    )

    parser.add_argument(
        'command',
        choices=['load-and-sync', 'load-local', 'sync-to-neon', 'verify'],
        help='Command to execute'
    )

    args = parser.parse_args()

    if args.command == 'load-and-sync':
        load_and_sync()
    elif args.command == 'load-local':
        load_local()
    elif args.command == 'sync-to-neon':
        sync_to_neon()
    elif args.command == 'verify':
        verify()

    return 0


if __name__ == '__main__':
    sys.exit(main())
