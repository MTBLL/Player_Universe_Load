#!/usr/bin/env python3
"""Main entry point for loading fantasy baseball data."""

import json
import sys
from datetime import datetime
from pathlib import Path

from .db import get_connection, init_schema
from .loaders.players import load_players
from .loaders.leagues import load_league
from .loaders.matchups import load_matchups
from .loaders.position_summary import load_all_position_summaries
from .loaders.teams import load_team_roster
from .validation import validate_data_schema


# ETL pipeline directories
TRANSFORM_DIR = Path("/Users/Shared/BaseballHQ/resources/transform")
LOAD_DIR = Path("/Users/Shared/BaseballHQ/resources/load")

# Fallback to test fixtures if pipeline dirs don't exist
FIXTURES_DIR = Path("tests/fixtures")


def load_all(year: int | None = None):
    """Load all data from ETL pipeline or test fixtures into the database."""
    season_id = year or datetime.now().year
    print(f"   📅 Season: {season_id}\n")

    # Determine which data source to use
    use_pipeline = TRANSFORM_DIR.exists() and LOAD_DIR.exists()

    if use_pipeline:
        print("🚀 Starting database load from ETL pipeline...\n")
        print(f"   📁 Transform dir: {TRANSFORM_DIR}")
        print(f"   📁 Load dir: {LOAD_DIR}\n")
    else:
        print("🚀 Starting database load from test fixtures...\n")
        print(f"   📁 Fixtures dir: {FIXTURES_DIR}\n")

    conn = get_connection()
    try:
        # Initialize schema
        print("\n📋 Initializing schema...")
        init_schema(conn)
        print()

        # Determine data directories
        if use_pipeline:
            player_dir = LOAD_DIR
            data_dir = TRANSFORM_DIR
            validation_dir = TRANSFORM_DIR  # Use transform dir for validation
        else:
            player_dir = FIXTURES_DIR
            data_dir = FIXTURES_DIR
            validation_dir = FIXTURES_DIR

        # Validate data schema matches DB schema
        validate_data_schema(conn, validation_dir)

        # Load players (hitters and pitchers) - from LOAD directory
        print("👥 Loading players...")
        hitters_file = player_dir / "hitters.json"
        pitchers_file = player_dir / "pitchers.json"

        if hitters_file.exists():
            print(f"   📄 Reading {hitters_file}")
            hitters = json.loads(hitters_file.read_text())
            counts = load_players(conn, hitters, season_id=season_id)
            print(f"  ✓ Hitters: {counts['players']} players, {counts['batting']} stat records")
            print(f"    {counts['projections']} projections, {counts['valuations']} valuations")
        else:
            print(f"   ⚠️  Hitters file not found: {hitters_file}")

        if pitchers_file.exists():
            print(f"   📄 Reading {pitchers_file}")
            pitchers = json.loads(pitchers_file.read_text())
            counts = load_players(conn, pitchers, season_id=season_id)
            print(f"  ✓ Pitchers: {counts['players']} players, {counts['pitching']} stat records")
            print(f"    {counts['projections']} projections, {counts['valuations']} valuations")
        else:
            print(f"   ⚠️  Pitchers file not found: {pitchers_file}")

        print()

        # Load league - from TRANSFORM directory
        print("🏆 Loading league...")
        league_file = data_dir / "league_10998_summary.json"
        if league_file.exists():
            print(f"   📄 Reading {league_file}")
            league = json.loads(league_file.read_text())
            counts = load_league(conn, league)
            print(f"  ✓ League {league['league_id']}: {counts['scoring_categories']} scoring categories")
        else:
            print(f"   ⚠️  League file not found: {league_file}")
        print()

        # Load teams FIRST (before matchups) - from TRANSFORM directory
        print("⚾ Loading teams...")
        team_files = sorted(data_dir.glob("team_*_roster.json"))
        if not team_files:
            print(f"   ⚠️  No team files found in {data_dir}")
        total_rosters = 0
        for team_file in team_files:
            team = json.loads(team_file.read_text())
            counts = load_team_roster(conn, team)
            total_rosters += counts["roster_slots"]
            print(f"  ✓ Team {team['team_id']} ({team['team_name']}): {counts['roster_slots']} roster slots")
        if team_files:
            print(f"\n  Total: {len(team_files)} teams, {total_rosters} roster slots")
        print()

        # Load per-position auction-pricing aggregates - from LOAD subdirs
        print("📐 Loading position summaries...")
        ps_counts = load_all_position_summaries(conn, player_dir)
        if ps_counts["position_summary"]:
            print(f"  ✓ Loaded {ps_counts['position_summary']} position_summary rows "
                  f"across 5 scenarios")
        else:
            print("   ⚠️  No position_summary.csv files found "
                  f"under {player_dir}/<scenario>/")
        print()

        # Load schedule/matchups (after teams) - from TRANSFORM directory
        print("📅 Loading schedule...")
        schedule_file = data_dir / "league_10998_schedule.json"
        if schedule_file.exists():
            print(f"   📄 Reading {schedule_file}")
            schedule = json.loads(schedule_file.read_text())
            count = load_matchups(conn, schedule)
            print(f"  ✓ Loaded {count} matchups")
        else:
            print(f"   ⚠️  Schedule file not found: {schedule_file}")
        print()

        print("\n✅ Load complete!\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    """Main CLI entry point - delegates to cli.py for command handling."""
    # If run directly without arguments, show usage
    if len(sys.argv) == 1:
        print("Usage: uv run player-universe-load <command>")
        print("\nCommands:")
        print("  load-and-sync  - Load locally and sync to Neon (full workflow)")
        print("  load-local     - Load to local PostgreSQL only")
        print("  sync-to-neon   - Sync local database to Neon")
        print("  verify         - Verify database structure and data")
        print("\nExamples:")
        print("  uv run player-universe-load load-and-sync")
        print("  uv run player-universe-load load-local")
        return 0

    # Delegate to CLI
    from .cli import main as cli_main
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
