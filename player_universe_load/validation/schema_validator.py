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

# Top-level keys the league summary loader (loaders/leagues.py) consumes.
LEAGUE_SUMMARY_KEYS = {
    "league_id",
    "season_id",
    "league_name",
    "scoring_period_id",
    "num_teams",
    "acquisition_budget",
    "draft_auction_budget",
    "roster_settings",
    "scoring_categories",
    "games_started_limits",
}

# Per-matchup keys the schedule loader (loaders/matchups.py) consumes.
MATCHUP_KEYS = {
    "matchup_id",
    "period_id",
    "is_playoff",
    "is_bye_week",
    "team1_id",
    "team1_score",
    "team2_id",
    "team2_score",
    "winner_id",
    "team1_categories",
    "team2_categories",
    "team1_games_started",
    "team2_games_started",
}

# Roster files (team_*_roster.json) are single-team objects. The 11 position
# fields each hold a list (or single) of roster-player objects.
ROSTER_POSITION_FIELDS = (
    "c", "first_base", "second_base", "third_base", "shortstop", "util",
    "outfield", "sp", "rp", "bench", "injured_list",
)

# Top-level keys the team loader (loaders/teams.py) consumes.
ROSTER_KEYS = {
    "league_id",
    "season_id",
    "team_id",
    "team_name",
    "team_abbrev",
    "team_logo",
    "owners",
    "primary_owner",
    "record",
    "transactions",
    *ROSTER_POSITION_FIELDS,
}

# Per-roster-player keys. Broader than what the loader stores: bio fields
# (name, pro_team, jersey, ...) are intentionally skipped because they
# FK-join from `players`. This is the full known shape of trx's
# RosterSlotPlayer, so the warning fires only on a genuinely new key.
ROSTER_PLAYER_KEYS = {
    "player_id",
    "name",
    "first_name",
    "last_name",
    "pro_team",
    "primary_position",
    "eligible_positions",
    "lineup_slot",
    "acquisition_type",
    "acquisition_date",
    "injury_status",
    "active",
    "keeper_value",
    "jersey",
    "eligible_date_by_position",
}


def _warn_unknown_keys(fixtures_dir: Path) -> None:
    """Soft-warn when upstream league/roster files carry keys no loader consumes.

    Unlike the table-column checks this never raises: a new upstream field
    should not break a load, but it must not vanish silently either. The
    loaders pull fields by name, so an unrecognized key is data the pipeline
    is dropping on the floor — surface it so the schema can catch up.
    """
    for summary_file in sorted(fixtures_dir.glob("league_*_summary.json")):
        data = json.loads(summary_file.read_text())
        unknown = set(data) - LEAGUE_SUMMARY_KEYS
        if unknown:
            print(
                f"   ⚠️  {summary_file.name}: unhandled key(s) "
                f"{sorted(unknown)} — not loaded into `leagues`"
            )

    for schedule_file in sorted(fixtures_dir.glob("league_*_schedule.json")):
        data = json.loads(schedule_file.read_text())
        unknown: set[str] = set()
        for matchup in data.get("matchups", []):
            unknown |= set(matchup) - MATCHUP_KEYS
        if unknown:
            print(
                f"   ⚠️  {schedule_file.name}: unhandled matchup key(s) "
                f"{sorted(unknown)} — not loaded into `matchups`"
            )

    # Roster files drift at two levels: the team object and the per-player
    # objects nested in the position fields. The per-player level is the one
    # that bit us (eligible_date_by_position was silently dropped), so check
    # both — the team loader scans roster files but never warned on them.
    for roster_file in sorted(fixtures_dir.glob("team_*_roster.json")):
        data = json.loads(roster_file.read_text())
        unknown_top = set(data) - ROSTER_KEYS
        if unknown_top:
            print(
                f"   ⚠️  {roster_file.name}: unhandled key(s) "
                f"{sorted(unknown_top)} — not loaded into `teams`"
            )

        unknown_player: set[str] = set()
        for field in ROSTER_POSITION_FIELDS:
            players = data.get(field)
            if players is None:
                continue
            if not isinstance(players, list):
                players = [players]
            for player in players:
                if isinstance(player, dict):
                    unknown_player |= set(player) - ROSTER_PLAYER_KEYS
        if unknown_player:
            print(
                f"   ⚠️  {roster_file.name}: unhandled roster-player key(s) "
                f"{sorted(unknown_player)} — not loaded into `roster_slots`"
            )


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

    # Soft-warn on upstream league/matchup keys no loader consumes.
    _warn_unknown_keys(fixtures_dir)

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
