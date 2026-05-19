#!/usr/bin/env python3
"""Validate fixture data schema against database schema."""

import json
from pathlib import Path

from ..db import validate_schema
from ..loaders.players import BATTING_DB_COLUMNS, PITCHING_DB_COLUMNS

# Define expected columns for each table based on loader code
PLAYER_COLUMNS = [
    "id_espn",
    "id_fangraphs",
    "id_xmlbam",
    "name",
    "first_name",
    "last_name",
    "name_ascii",
    "slug",
    "fangraphs_api_route",
    "headshot",
    "primary_position",
    "eligible_slots",
    "pro_team",
    "weight",
    "display_weight",
    "height",
    "display_height",
    "bats",
    "throws",
    "date_of_birth",
    "birth_place",
    "debut_year",
    "injury_status",
    "status",
    "injured",
    "active",
    "jersey",
]

# Sourced from the spec in loaders/players.py to avoid drift.
BATTING_STAT_COLUMNS = ["player_id", "season_id", "stat_period"] + list(BATTING_DB_COLUMNS)
PITCHING_STAT_COLUMNS = ["player_id", "season_id", "stat_period"] + list(PITCHING_DB_COLUMNS)


def validate_data_schema(conn, fixtures_dir: Path) -> bool:
    """
    Validate that fixture data structure matches database schema.

    Returns True if valid, raises SystemExit if mismatches found.
    """
    print("🔍 Validating data schema compatibility...")
    schema_issues = []

    # Check hitters file
    hitters_file = fixtures_dir / "hitters.json"
    if hitters_file.exists():
        print("   Checking hitters.json...")
        data = json.loads(hitters_file.read_text())
        if data and len(data) > 0:
            sample = data[0]

            # Validate player table
            is_valid, missing, extra = validate_schema(conn, "players", PLAYER_COLUMNS)
            if not is_valid:
                schema_issues.append(("players", missing, extra))

            # Validate batting stats if present (new nested shape: stats.espn.current_season)
            espn_cs = (
                (sample.get("stats") or {}).get("espn", {}).get("current_season")
                or {}
            )
            if "AB" in espn_cs or "AVG" in espn_cs:
                is_valid, missing, extra = validate_schema(
                    conn, "player_stats_batting", BATTING_STAT_COLUMNS
                )
                if not is_valid:
                    schema_issues.append(
                        ("player_stats_batting", missing, extra)
                    )

    # Check pitchers file
    pitchers_file = fixtures_dir / "pitchers.json"
    if pitchers_file.exists():
        print("   Checking pitchers.json...")
        data = json.loads(pitchers_file.read_text())
        if data and len(data) > 0:
            sample = data[0]

            # Validate pitching stats if present (new nested shape: stats.espn.current_season)
            espn_cs = (
                (sample.get("stats") or {}).get("espn", {}).get("current_season")
                or {}
            )
            if "IP" in espn_cs or "ERA" in espn_cs:
                is_valid, missing, extra = validate_schema(
                    conn, "player_stats_pitching", PITCHING_STAT_COLUMNS
                )
                if not is_valid:
                    schema_issues.append(
                        ("player_stats_pitching", missing, extra)
                    )

    # Report issues
    if schema_issues:
        print("\n❌ SCHEMA MISMATCH DETECTED!\n")
        for table, missing, extra in schema_issues:
            print(f"📋 Table: {table}")
            if missing:
                print("   ⚠️  Missing in DB (need to add these columns):")
                for col in missing:
                    print(f"      - {col}")
            if extra:
                print("   ℹ️  In DB but not in data (unused columns):")
                for col in extra:
                    print(f"      - {col}")
            print()

        print("⚠️  ACTION REQUIRED:")
        print("    Update schema files in player_universe_load/schemas/")
        print("    to match your upstream data structure.\n")
        raise SystemExit(1)

    print("   ✓ Schema validation passed\n")
    return True
