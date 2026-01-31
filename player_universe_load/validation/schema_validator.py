#!/usr/bin/env python3
"""Validate fixture data schema against database schema."""

import json
from pathlib import Path

from ..db import validate_schema

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

BATTING_STAT_COLUMNS = [
    "player_id",
    "season_id",
    "stat_period",
    "G",
    "AB",
    "PA",
    "H",
    "singles",
    "doubles",
    "triples",
    "HR",
    "XBH",
    "TB",
    "R",
    "RBI",
    "SB",
    "CS",
    "SBN",
    "BB",
    "IBB",
    "HBP",
    "SF",
    "SAC",
    "SO",
    "GDP",
    "AVG",
    "OBP",
    "SLG",
    "OPS",
    "BABIP",
    "ISO",
    "wOBA",
    "exit_velo",
    "adj_exit_velo",
    "launch_angle",
    "attack_angle",
    "attack_dir",
    "bat_speed",
    "swing_length",
    "swing_path_tilt",
    "swing_miss_pct",
    "swings",
    "takes",
    "whiffs",
    "barrel_rate",
    "barrels_per_bbe_pct",
    "barrels_per_pa_pct",
    "barrels_total",
    "hard_hit_rate",
    "hardhit_pct",
    "batter_run_value_per_100",
    "xAVG",
    "xOBP",
    "xSLG",
    "xwOBA",
    "xAVGdiff",
    "xOBPdiff",
    "xSLGdiff",
    "BB_pct",
    "K_pct",
    "BBdist",
    "Kdist",
]

PITCHING_STAT_COLUMNS = [
    "player_id",
    "season_id",
    "stat_period",
    "GP",
    "GS",
    "OUTS",
    "IP",
    "TBF",
    "H",
    "R",
    "ER",
    "HR",
    "BB",
    "IBB",
    "K",
    "HBP",
    "WP",
    "BK",
    "W",
    "L",
    "WPCT",
    "QS",
    "SV",
    "HLD",
    "SVHD",
    "SVO",
    "BLSV",
    "SV_pct",
    "ERA",
    "WHIP",
    "OBA",
    "OOBP",
    "k_bb_ratio",
    "k_per_9",
    "bb_per_9",
    "velo",
    "spin_rate",
    "eff_min_vel",
    "percieved_velo",
    "release_extension",
    "release_pos_x",
    "release_pos_z",
    "break_z",
    "induced_break_z",
    "break_x_arm_side",
    "break_x_batter_in",
    "arm_angle",
    "pitcher_run_exp",
    "pitcher_run_value_per_100",
    "exit_velo",
    "adj_exit_velo",
    "launch_angle",
    "swing_miss_pct",
    "swings",
    "takes",
    "whiffs",
    "xAVG",
    "xOBP",
    "xSLG",
    "xwOBA",
    "xAVGdiff",
    "xOBPdiff",
    "xSLGdiff",
]


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

            # Validate batting stats if present
            if "stats" in sample and sample["stats"]:
                if (
                    "current_season" in sample["stats"]
                    and sample["stats"]["current_season"]
                ):
                    cs = sample["stats"]["current_season"]
                    if "AB" in cs or "AVG" in cs:
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

            # Validate pitching stats if present
            if "stats" in sample and sample["stats"]:
                if (
                    "current_season" in sample["stats"]
                    and sample["stats"]["current_season"]
                ):
                    cs = sample["stats"]["current_season"]
                    if "IP" in cs or "ERA" in cs:
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
