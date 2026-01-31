#!/usr/bin/env python3
"""Main entry point for loading fantasy baseball data."""

import json
import sys
from pathlib import Path

from .db import get_connection, init_schema
from .loaders.players import load_players
from .loaders.leagues import load_league
from .loaders.matchups import load_matchups
from .loaders.teams import load_team_roster
from .validation import validate_data_schema


FIXTURES_DIR = Path("tests/fixtures")


def load_all():
    """Load all fixture data into the database."""
    print("🚀 Starting database load...\n")

    conn = get_connection()
    try:
        # Initialize schema
        print("\n📋 Initializing schema...")
        init_schema(conn)
        print()

        # Validate data schema matches DB schema
        validate_data_schema(conn, FIXTURES_DIR)

        # Load players (hitters and pitchers)
        print("👥 Loading players...")
        hitters_file = FIXTURES_DIR / "hitters.json"
        pitchers_file = FIXTURES_DIR / "pitchers.json"

        if hitters_file.exists():
            hitters = json.loads(hitters_file.read_text())
            counts = load_players(conn, hitters, season_id=2025)
            print(f"  ✓ Hitters: {counts['players']} players, {counts['batting']} stat records")
            print(f"    {counts['projections']} projections, {counts['valuations']} valuations")

        if pitchers_file.exists():
            pitchers = json.loads(pitchers_file.read_text())
            counts = load_players(conn, pitchers, season_id=2025)
            print(f"  ✓ Pitchers: {counts['players']} players, {counts['pitching']} stat records")
            print(f"    {counts['projections']} projections, {counts['valuations']} valuations")

        print()

        # Load league
        print("🏆 Loading league...")
        league_file = FIXTURES_DIR / "league_10998_summary.json"
        if league_file.exists():
            league = json.loads(league_file.read_text())
            counts = load_league(conn, league)
            print(f"  ✓ League {league['league_id']}: {counts['scoring_categories']} scoring categories")
        print()

        # Load teams FIRST (before matchups, since matchups reference teams)
        print("⚾ Loading teams...")
        team_files = sorted(FIXTURES_DIR.glob("team_*_roster.json"))
        total_rosters = 0
        for team_file in team_files:
            team = json.loads(team_file.read_text())
            counts = load_team_roster(conn, team)
            total_rosters += counts["roster_slots"]
            print(f"  ✓ Team {team['team_id']} ({team['team_name']}): {counts['roster_slots']} roster slots")
        print(f"\n  Total: {len(team_files)} teams, {total_rosters} roster slots")
        print()

        # Load schedule/matchups (after teams)
        print("📅 Loading schedule...")
        schedule_file = FIXTURES_DIR / "league_10998_schedule.json"
        if schedule_file.exists():
            schedule = json.loads(schedule_file.read_text())
            count = load_matchups(conn, schedule)
            print(f"  ✓ Loaded {count} matchups")
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
        print("Usage: uv run -m player_universe_load <command>")
        print("\nCommands:")
        print("  load-and-sync  - Load locally and sync to Neon (full workflow)")
        print("  load-local     - Load to local PostgreSQL only")
        print("  sync-to-neon   - Sync local database to Neon")
        print("  verify         - Verify database structure and data")
        print("\nExamples:")
        print("  uv run -m player_universe_load load-and-sync")
        print("  uv run -m player_universe_load load-local")
        return 0

    # Delegate to CLI
    from .cli import main as cli_main
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
