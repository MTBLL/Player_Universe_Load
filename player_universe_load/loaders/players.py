#!/usr/bin/env python3
"""Load players and their stats into the database."""

from typing import Any
from ..db import bulk_insert, json_serialize


def load_players(conn, data: list[dict[str, Any]], season_id: int = 2025) -> dict[str, int]:
    """Load players, their stats, projections, and valuations."""
    print(f"   📊 Processing {len(data):,} players...", flush=True)
    counts = {"players": 0, "batting": 0, "pitching": 0, "projections": 0, "valuations": 0}

    player_rows = []
    batting_rows = []
    pitching_rows = []
    projection_rows = []
    valuation_rows = []
    valuation_detail_rows = []

    # Show progress every 10%
    progress_interval = max(1, len(data) // 10)

    for idx, player in enumerate(data):
        if idx > 0 and idx % progress_interval == 0:
            pct = (idx / len(data)) * 100
            print(f"   ⏳ Processing... {idx:,}/{len(data):,} ({pct:.0f}%)", flush=True)
        # Basic player info
        player_rows.append((
            player["id_espn"],
            player.get("id_fangraphs"),
            player.get("id_xmlbam"),
            player["name"],
            player.get("first_name"),
            player.get("last_name"),
            player.get("name_ascii"),
            player.get("slug"),
            player.get("fangraphs_api_route"),
            player.get("headshot"),
            player.get("primary_position"),
            json_serialize(player.get("eligible_slots")),
            player.get("pro_team"),
            player.get("weight"),
            player.get("display_weight"),
            player.get("height"),
            player.get("display_height"),
            player.get("bats"),
            player.get("throws"),
            player.get("date_of_birth"),
            json_serialize(player.get("birth_place")),
            player.get("debut_year"),
            player.get("injury_status"),
            player.get("status"),
            player.get("injured"),
            player.get("active"),
            player.get("jersey"),
        ))

        # Stats
        if "stats" in player:
            stats = player["stats"]

            # Current season stats
            if "current_season" in stats and stats["current_season"]:
                cs = stats["current_season"]
                # Determine if batting or pitching stats
                if "AB" in cs or "AVG" in cs:
                    batting_rows.append(_build_batting_row(player["id_espn"], season_id, "current_season", cs))
                elif "IP" in cs or "ERA" in cs:
                    pitching_rows.append(_build_pitching_row(player["id_espn"], season_id, "current_season", cs))

            # ESPN stats (multiple periods)
            if "espn_stats" in stats:
                for period, period_stats in stats["espn_stats"].items():
                    if not period_stats:  # Skip if None or empty
                        continue
                    if "AB" in period_stats or "AVG" in period_stats:
                        batting_rows.append(_build_batting_row(player["id_espn"], season_id, f"espn_{period}", period_stats))
                    elif "IP" in period_stats or "ERA" in period_stats:
                        pitching_rows.append(_build_pitching_row(player["id_espn"], season_id, f"espn_{period}", period_stats))

            # Projections
            if "projections" in stats:
                proj = stats["projections"]
                player_type = "hitter" if "AB" in proj else "pitcher"
                projection_rows.append((
                    player["id_espn"],
                    season_id,
                    "fangraphs",
                    player_type,
                    json_serialize(proj),
                ))

        # Valuations
        if "valuations" in player:
            val = player["valuations"]
            valuation_rows.append((
                player["id_espn"],
                None,  # league_id (NULL for universal valuations)
                season_id,
                val.get("primary_position"),
                val.get("tier"),
                val.get("total_z"),
                val.get("total_dollars"),
            ))

            # Valuation details will be inserted after getting valuation IDs

    # Bulk insert
    print(f"\n   📝 Prepared {len(player_rows):,} player records")
    print(f"   📝 Prepared {len(batting_rows):,} batting stat records")
    print(f"   📝 Prepared {len(pitching_rows):,} pitching stat records")
    print(f"   📝 Prepared {len(projection_rows):,} projection records")
    print(f"   📝 Prepared {len(valuation_rows):,} valuation records\n")

    counts["players"] = bulk_insert(conn, "players", [
        "id_espn", "id_fangraphs", "id_xmlbam", "name", "first_name", "last_name",
        "name_ascii", "slug", "fangraphs_api_route", "headshot", "primary_position",
        "eligible_slots", "pro_team", "weight", "display_weight", "height",
        "display_height", "bats", "throws", "date_of_birth", "birth_place",
        "debut_year", "injury_status", "status", "injured", "active", "jersey"
    ], player_rows)

    if batting_rows:
        # Build column list from the stats fields
        stat_cols = ["G", "AB", "PA", "H", "singles", "doubles", "triples", "HR",
                     "XBH", "TB", "R", "RBI", "SB", "CS", "SBN", "BB", "IBB", "HBP",
                     "SF", "SAC", "SO", "GDP", "AVG", "OBP", "SLG", "OPS", "BABIP",
                     "ISO", "wOBA", "exit_velo", "adj_exit_velo", "launch_angle",
                     "attack_angle", "attack_dir", "bat_speed", "swing_length",
                     "swing_path_tilt", "swing_miss_pct", "swings", "takes", "whiffs",
                     "barrel_rate", "barrels_per_bbe_pct", "barrels_per_pa_pct",
                     "barrels_total", "hard_hit_rate", "hardhit_pct",
                     "batter_run_value_per_100", "xAVG", "xOBP", "xSLG", "xwOBA",
                     "xAVGdiff", "xOBPdiff", "xSLGdiff", "BB_pct", "K_pct", "BBdist", "Kdist"]
        counts["batting"] = bulk_insert(conn, "player_stats_batting",
            ["player_id", "season_id", "stat_period"] + stat_cols,
            batting_rows
        )

    if pitching_rows:
        # Build column list from the stats fields
        stat_cols = ["GP", "GS", "OUTS", "IP", "TBF", "H", "R", "ER", "HR", "BB",
                     "IBB", "K", "HBP", "WP", "BK", "W", "L", "WPCT", "QS", "SV",
                     "HLD", "SVHD", "SVO", "BLSV", "SV_pct", "ERA", "WHIP", "OBA",
                     "OOBP", "k_bb_ratio", "k_per_9", "bb_per_9", "velo", "spin_rate",
                     "eff_min_vel", "percieved_velo", "release_extension",
                     "release_pos_x", "release_pos_z", "break_z", "induced_break_z",
                     "break_x_arm_side", "break_x_batter_in", "arm_angle",
                     "pitcher_run_exp", "pitcher_run_value_per_100", "exit_velo",
                     "adj_exit_velo", "launch_angle", "swing_miss_pct", "swings",
                     "takes", "whiffs", "xAVG", "xOBP", "xSLG", "xwOBA", "xAVGdiff",
                     "xOBPdiff", "xSLGdiff"]
        counts["pitching"] = bulk_insert(conn, "player_stats_pitching",
            ["player_id", "season_id", "stat_period"] + stat_cols,
            pitching_rows
        )

    if projection_rows:
        counts["projections"] = bulk_insert(conn, "player_projections",
            ["player_id", "season_id", "projection_source", "player_type", "projections"],
            projection_rows
        )

    if valuation_rows:
        counts["valuations"] = bulk_insert(conn, "player_valuations",
            ["player_id", "league_id", "season_id", "primary_position", "tier", "total_z", "total_dollars"],
            valuation_rows
        )

        # Now handle valuation details
        with conn.cursor() as cur:
            for player in data:
                if "valuations" in player and "z_scores" in player["valuations"]:
                    cur.execute(
                        "SELECT id FROM player_valuations WHERE player_id = %s AND season_id = %s AND league_id IS NULL",
                        (player["id_espn"], season_id)
                    )
                    result = cur.fetchone()
                    if result:
                        valuation_id = result[0]
                        for stat_cat, z_score in player["valuations"]["z_scores"].items():
                            dollar_val = player["valuations"]["dollar_values"].get(stat_cat)
                            valuation_detail_rows.append((valuation_id, stat_cat, z_score, dollar_val))

        if valuation_detail_rows:
            bulk_insert(conn, "player_valuation_details",
                ["valuation_id", "stat_category", "z_score", "dollar_value"],
                valuation_detail_rows
            )

    return counts


def _build_batting_row(player_id: int, season_id: int, period: str, stats: dict) -> tuple:
    """Build batting stats row."""
    return (
        player_id, season_id, period,
        stats.get("G"), stats.get("AB"), stats.get("PA"), stats.get("H"),
        stats.get("singles"), stats.get("doubles"), stats.get("triples"), stats.get("HR"),
        stats.get("XBH"), stats.get("TB"), stats.get("R"), stats.get("RBI"),
        stats.get("SB"), stats.get("CS"), stats.get("SBN"), stats.get("BB") or stats.get("B_BB"),
        stats.get("IBB") or stats.get("B_IBB"), stats.get("HBP"), stats.get("SF"), stats.get("SAC"),
        stats.get("SO") or stats.get("B_SO"), stats.get("GDP"),
        stats.get("AVG"), stats.get("OBP"), stats.get("SLG"), stats.get("OPS"),
        stats.get("BABIP"), stats.get("ISO"), stats.get("wOBA"),
        stats.get("exit_velo"), stats.get("adj_exit_velo"), stats.get("launch_angle"),
        stats.get("attack_angle"), stats.get("attack_dir"), stats.get("bat_speed"),
        stats.get("swing_length"), stats.get("swing_path_tilt"), stats.get("swing_miss_pct"),
        stats.get("swings"), stats.get("takes"), stats.get("whiffs"),
        stats.get("barrel_rate"), stats.get("barrels_per_bbe_pct"), stats.get("barrels_per_pa_pct"),
        stats.get("barrels_total"), stats.get("hard_hit_rate"), stats.get("hardhit_pct"),
        stats.get("batter_run_value_per_100"),
        stats.get("xAVG"), stats.get("xOBP"), stats.get("xSLG"), stats.get("xwOBA"),
        stats.get("xAVGdiff"), stats.get("xOBPdiff"), stats.get("xSLGdiff"),
        stats.get("BB_pct"), stats.get("K_pct"), stats.get("BBdist"), stats.get("Kdist"),
    )


def _build_pitching_row(player_id: int, season_id: int, period: str, stats: dict) -> tuple:
    """Build pitching stats row."""
    return (
        player_id, season_id, period,
        stats.get("GP"), stats.get("GS"), stats.get("OUTS"), stats.get("IP"),
        stats.get("TBF"), stats.get("H") or stats.get("P_H"), stats.get("R") or stats.get("P_R"),
        stats.get("ER"), stats.get("HR") or stats.get("P_HR"), stats.get("BB") or stats.get("P_BB"),
        stats.get("IBB") or stats.get("P_IBB"), stats.get("K"), stats.get("HBP"),
        stats.get("WP"), stats.get("BK"),
        stats.get("W"), stats.get("L"), stats.get("WPCT"), stats.get("QS"),
        stats.get("SV"), stats.get("HLD"), stats.get("SVHD"), stats.get("SVO"),
        stats.get("BLSV"), stats.get("SV_pct"),
        stats.get("ERA"), stats.get("WHIP"), stats.get("OBA"), stats.get("OOBP"),
        stats.get("k_bb_ratio"), stats.get("k_per_9"), stats.get("bb_per_9"),
        stats.get("velo"), stats.get("spin_rate"), stats.get("eff_min_vel"),
        stats.get("percieved_velo"), stats.get("release_extension"),
        stats.get("release_pos_x"), stats.get("release_pos_z"),
        stats.get("break_z"), stats.get("induced_break_z"),
        stats.get("break_x_arm_side"), stats.get("break_x_batter_in"), stats.get("arm_angle"),
        stats.get("pitcher_run_exp"), stats.get("pitcher_run_value_per_100"),
        stats.get("exit_velo"), stats.get("adj_exit_velo"), stats.get("launch_angle"),
        stats.get("swing_miss_pct"), stats.get("swings"), stats.get("takes"), stats.get("whiffs"),
        stats.get("xAVG"), stats.get("xOBP"), stats.get("xSLG"), stats.get("xwOBA"),
        stats.get("xAVGdiff"), stats.get("xOBPdiff"), stats.get("xSLGdiff"),
    )
