#!/usr/bin/env python3
"""Load players and their stats into the database."""

from typing import Any
from ..db import bulk_insert, json_serialize


# New nested stats shape: stats.{espn,fangraphs,savant}.{period}
ESPN_PERIOD_LABELS = {
    "projections": "espn_proj",
    "current_season": "espn_current",
    "previous_season": "espn_previous",
    "last_7_games": "espn_last_7",
    "last_15_games": "espn_last_15",
    "last_30_games": "espn_last_30",
}
SAVANT_TABULAR_LABELS = {
    "all": "savant_all",
    "vs_r": "savant_vs_r",
    "vs_l": "savant_vs_l",
}
FANGRAPHS_PERIOD_LABELS = {
    "projections": "preseason",
    "projs_updated": "updated",
    "ros": "ros",
}
SAVANT_BLOB_PERIODS = (
    "statcast",
    "home_runs",
    "sprint_speed",
    "swing_take",
    "expected_statistics",
    "pitch_arsenal",
)

# Stat-key markers used to infer player_type when the explicit marker is
# absent or unrecognized. Order matters: prefer ESPN/Fangraphs current_season,
# then projections, then anything else.
_BATTER_STAT_KEYS = frozenset(("AB", "AVG", "B_BB", "B_SO", "OBP", "SLG", "singles"))
_PITCHER_STAT_KEYS = frozenset(("IP", "ERA", "WHIP", "K", "ER", "P_H", "P_BB", "P_HR", "P_R"))


def _infer_player_type(player: dict) -> str:
    """Return 'batter' or 'pitcher'.

    Honor an explicit ``player_type`` of 'batter'/'hitter' or 'pitcher' when
    present; otherwise sniff stat keys across nested stats sources/periods to
    decide. Defaults to 'pitcher' only as a last resort when no stat evidence
    is found in either direction.
    """
    explicit = (player.get("player_type") or "").lower()
    if explicit in ("batter", "hitter"):
        return "batter"
    if explicit == "pitcher":
        return "pitcher"

    stats = player.get("stats") or {}
    # Probe in priority order: espn periods, fangraphs periods, savant tabular.
    candidates: list[dict] = []
    for src_key, periods in (
        ("espn", ESPN_PERIOD_LABELS.keys()),
        ("fangraphs", FANGRAPHS_PERIOD_LABELS.keys()),
        ("savant", SAVANT_TABULAR_LABELS.keys()),
    ):
        src = stats.get(src_key) or {}
        for p in periods:
            v = src.get(p)
            if isinstance(v, dict) and v:
                candidates.append(v)

    for c in candidates:
        keys = c.keys()
        if _BATTER_STAT_KEYS & keys:
            return "batter"
        if _PITCHER_STAT_KEYS & keys:
            return "pitcher"

    return "pitcher"

# Spec-driven row builders. Each entry is (db_column, (json_alias, ...)).
# First non-None alias wins. Adding a new field = add a single tuple.
BATTING_COLUMN_SPEC: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("G", ("G",)),
    ("AB", ("AB",)),
    ("PA", ("PA",)),
    ("H", ("H",)),
    ("singles", ("singles",)),
    ("doubles", ("doubles",)),
    ("triples", ("triples",)),
    ("HR", ("HR",)),
    ("XBH", ("XBH",)),
    ("TB", ("TB",)),
    ("R", ("R",)),
    ("RBI", ("RBI",)),
    ("SB", ("SB",)),
    ("CS", ("CS",)),
    ("SBN", ("SBN",)),
    ("BB", ("BB", "B_BB")),
    ("IBB", ("IBB", "B_IBB")),
    ("HBP", ("HBP",)),
    ("SF", ("SF",)),
    ("SAC", ("SAC",)),
    ("SO", ("SO", "B_SO", "K")),
    ("GDP", ("GDP",)),
    ("AVG", ("AVG",)),
    ("OBP", ("OBP",)),
    ("SLG", ("SLG",)),
    ("OPS", ("OPS",)),
    ("BABIP", ("BABIP",)),
    ("ISO", ("ISO",)),
    ("wOBA", ("wOBA",)),
    ("exit_velo", ("exit_velo",)),
    ("adj_exit_velo", ("adj_exit_velo",)),
    ("launch_angle", ("launch_angle",)),
    ("attack_angle", ("attack_angle",)),
    ("attack_dir", ("attack_dir",)),
    ("bat_speed", ("bat_speed",)),
    ("swing_length", ("swing_length",)),
    ("swing_path_tilt", ("swing_path_tilt",)),
    ("swing_miss_pct", ("swing_miss_pct",)),
    ("swings", ("swings",)),
    ("takes", ("takes",)),
    ("whiffs", ("whiffs",)),
    ("barrel_rate", ("barrel_rate",)),
    ("barrels_per_bbe_pct", ("barrels_per_bbe_pct",)),
    ("barrels_per_pa_pct", ("barrels_per_pa_pct",)),
    ("barrels_total", ("barrels_total",)),
    ("hard_hit_rate", ("hard_hit_rate",)),
    ("hardhit_pct", ("hardhit_pct",)),
    ("batter_run_value_per_100", ("batter_run_value_per_100",)),
    ("xAVG", ("xAVG",)),
    ("xOBP", ("xOBP",)),
    ("xSLG", ("xSLG",)),
    ("xwOBA", ("xwOBA",)),
    ("xAVGdiff", ("xAVGdiff",)),
    ("xOBPdiff", ("xOBPdiff",)),
    ("xSLGdiff", ("xSLGdiff",)),
    ("BB_pct", ("BB_pct",)),
    ("K_pct", ("K_pct",)),
    ("BBdist", ("BBdist",)),
    ("Kdist", ("Kdist",)),
    # New Savant fields (added per "store everything" directive)
    ("BIP", ("BIP",)),
    ("pitches", ("pitches",)),
    ("total_pitches", ("total_pitches",)),
    ("pitch_percent", ("pitch_percent",)),
    ("run_exp", ("run_exp",)),
    ("rate_ideal_attack_angle", ("rate_ideal_attack_angle",)),
    ("percieved_velo", ("percieved_velo",)),
    ("pitch_velo", ("pitch_velo",)),
    ("wOBAdiff", ("wOBAdiff",)),
    ("barrels_per_bbe_pct_pct_rnk", ("barrels_per_bbe_pct_pct_rnk",)),
    ("barrels_per_pa_pct_pct_rnk", ("barrels_per_pa_pct_pct_rnk",)),
    ("barrels_total_pct_rnk", ("barrels_total_pct_rnk",)),
    ("hardhit_pct_pct_rnk", ("hardhit_pct_pct_rnk",)),
)

PITCHING_COLUMN_SPEC: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("GP", ("GP",)),
    ("GS", ("GS",)),
    ("OUTS", ("OUTS",)),
    ("IP", ("IP",)),
    ("TBF", ("TBF",)),
    ("H", ("H", "P_H")),
    ("R", ("R", "P_R")),
    ("ER", ("ER",)),
    ("HR", ("HR", "P_HR")),
    ("BB", ("BB", "P_BB")),
    ("IBB", ("IBB", "P_IBB")),
    ("K", ("K",)),
    ("HBP", ("HBP",)),
    ("WP", ("WP",)),
    ("BK", ("BK",)),
    ("W", ("W",)),
    ("L", ("L",)),
    ("WPCT", ("WPCT",)),
    ("QS", ("QS",)),
    ("SV", ("SV",)),
    ("HLD", ("HLD",)),
    ("SVHD", ("SVHD",)),
    ("SVO", ("SVO",)),
    ("BLSV", ("BLSV",)),
    ("SV_pct", ("SV_pct",)),
    ("ERA", ("ERA",)),
    ("WHIP", ("WHIP",)),
    ("OBA", ("OBA",)),
    ("OOBP", ("OOBP",)),
    ("k_bb_ratio", ("k_bb_ratio",)),
    ("k_per_9", ("k_per_9",)),
    ("bb_per_9", ("bb_per_9",)),
    ("velo", ("velo",)),
    ("spin_rate", ("spin_rate",)),
    ("eff_min_vel", ("eff_min_vel",)),
    ("percieved_velo", ("percieved_velo",)),
    ("release_extension", ("release_extension",)),
    ("release_pos_x", ("release_pos_x",)),
    ("release_pos_z", ("release_pos_z",)),
    ("break_z", ("break_z",)),
    ("induced_break_z", ("induced_break_z",)),
    ("break_x_arm_side", ("break_x_arm_side",)),
    ("break_x_batter_in", ("break_x_batter_in",)),
    ("arm_angle", ("arm_angle",)),
    ("pitcher_run_exp", ("pitcher_run_exp",)),
    ("pitcher_run_value_per_100", ("pitcher_run_value_per_100",)),
    ("exit_velo", ("exit_velo",)),
    ("adj_exit_velo", ("adj_exit_velo",)),
    ("launch_angle", ("launch_angle",)),
    ("swing_miss_pct", ("swing_miss_pct",)),
    ("swings", ("swings",)),
    ("takes", ("takes",)),
    ("whiffs", ("whiffs",)),
    ("xAVG", ("xAVG",)),
    ("xOBP", ("xOBP",)),
    ("xSLG", ("xSLG",)),
    ("xwOBA", ("xwOBA",)),
    ("xAVGdiff", ("xAVGdiff",)),
    ("xOBPdiff", ("xOBPdiff",)),
    ("xSLGdiff", ("xSLGdiff",)),
    # New Savant-against fields (rates the pitcher gave up)
    ("AVG", ("AVG",)),
    ("OBP", ("OBP",)),
    ("SLG", ("SLG",)),
    ("BABIP", ("BABIP",)),
    ("ISO", ("ISO",)),
    ("BB_pct", ("BB_pct",)),
    ("K_pct", ("K_pct",)),
    ("BBdist", ("BBdist",)),
    ("BIP", ("BIP",)),
    ("PA", ("PA",)),
    ("pitches", ("pitches",)),
    ("total_pitches", ("total_pitches",)),
    ("pitch_percent", ("pitch_percent",)),
    ("barrels_per_bbe_pct", ("barrels_per_bbe_pct",)),
    ("barrels_per_bbe_pct_pct_rnk", ("barrels_per_bbe_pct_pct_rnk",)),
    ("barrels_per_pa_pct", ("barrels_per_pa_pct",)),
    ("barrels_per_pa_pct_pct_rnk", ("barrels_per_pa_pct_pct_rnk",)),
    ("barrels_total", ("barrels_total",)),
    ("barrels_total_pct_rnk", ("barrels_total_pct_rnk",)),
    ("hardhit_pct", ("hardhit_pct",)),
    ("hardhit_pct_pct_rnk", ("hardhit_pct_pct_rnk",)),
    ("rate_ideal_attack_angle", ("rate_ideal_attack_angle",)),
    ("run_exp", ("run_exp",)),
    ("wOBA", ("wOBA",)),
    ("wOBAdiff", ("wOBAdiff",)),
)

BATTING_DB_COLUMNS: tuple[str, ...] = tuple(c[0] for c in BATTING_COLUMN_SPEC)
PITCHING_DB_COLUMNS: tuple[str, ...] = tuple(c[0] for c in PITCHING_COLUMN_SPEC)


def _extract(stats: dict, aliases: tuple[str, ...]) -> Any:
    """Return first non-None value from aliases; None if none match."""
    for a in aliases:
        v = stats.get(a)
        if v is not None:
            return v
    return None


def _build_batting_row(player_id: int, season_id: int, period: str, stats: dict) -> tuple:
    return (player_id, season_id, period) + tuple(
        _extract(stats, aliases) for _, aliases in BATTING_COLUMN_SPEC
    )


def _build_pitching_row(player_id: int, season_id: int, period: str, stats: dict) -> tuple:
    return (player_id, season_id, period) + tuple(
        _extract(stats, aliases) for _, aliases in PITCHING_COLUMN_SPEC
    )


def load_players(conn, data: list[dict[str, Any]], season_id: int) -> dict[str, int]:
    """Load players, their stats, projections, and valuations."""
    print(f"   📊 Processing {len(data):,} players...", flush=True)
    counts = {"players": 0, "batting": 0, "pitching": 0, "projections": 0, "valuations": 0}

    player_rows = []
    batting_rows = []
    pitching_rows = []
    projection_rows = []
    valuation_rows = []
    valuation_detail_rows = []

    progress_interval = max(1, len(data) // 10)

    for idx, player in enumerate(data):
        if idx > 0 and idx % progress_interval == 0:
            pct = (idx / len(data)) * 100
            print(f"   ⏳ Processing... {idx:,}/{len(data):,} ({pct:.0f}%)", flush=True)

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

        # Stats: stats.{espn,fangraphs,savant}.{period}
        # ESPN + Savant tabular -> batting/pitching rows. Fangraphs + Savant blobs -> projection rows (JSONB).
        stats = player.get("stats") or {}
        player_type = _infer_player_type(player)

        espn = stats.get("espn") or {}
        for espn_key, period_label in ESPN_PERIOD_LABELS.items():
            period_stats = espn.get(espn_key)
            if not period_stats:
                continue
            if player_type == "batter":
                batting_rows.append(_build_batting_row(player["id_espn"], season_id, period_label, period_stats))
            else:
                pitching_rows.append(_build_pitching_row(player["id_espn"], season_id, period_label, period_stats))

        savant = stats.get("savant") or {}
        for savant_key, period_label in SAVANT_TABULAR_LABELS.items():
            period_stats = savant.get(savant_key)
            if not period_stats:
                continue
            if player_type == "batter":
                batting_rows.append(_build_batting_row(player["id_espn"], season_id, period_label, period_stats))
            else:
                pitching_rows.append(_build_pitching_row(player["id_espn"], season_id, period_label, period_stats))

        fangraphs = stats.get("fangraphs") or {}
        for fg_key, period_label in FANGRAPHS_PERIOD_LABELS.items():
            proj = fangraphs.get(fg_key)
            if not proj:
                continue
            projection_rows.append((
                player["id_espn"],
                season_id,
                "fangraphs",
                period_label,
                "hitter" if player_type == "batter" else "pitcher",
                json_serialize(proj),
            ))

        for savant_blob_key in SAVANT_BLOB_PERIODS:
            blob = savant.get(savant_blob_key)
            if not blob:
                continue
            projection_rows.append((
                player["id_espn"],
                season_id,
                "savant",
                savant_blob_key,
                "hitter" if player_type == "batter" else "pitcher",
                json_serialize(blob),
            ))

        # Valuations: dict of scenario -> {primary_position, tier, total_z, total_dollars, z_scores, dollar_values}
        # Scenarios: preseason, updated, ros, synthetic, current
        if "valuations" in player and isinstance(player["valuations"], dict):
            for val_type, val in player["valuations"].items():
                if not val:
                    continue
                valuation_rows.append((
                    player["id_espn"],
                    season_id,
                    val_type,
                    val.get("primary_position"),
                    val.get("tier"),
                    val.get("total_z"),
                    val.get("total_dollars"),
                ))

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
        counts["batting"] = bulk_insert(conn, "player_stats_batting",
            ["player_id", "season_id", "stat_period"] + list(BATTING_DB_COLUMNS),
            batting_rows
        )

    if pitching_rows:
        counts["pitching"] = bulk_insert(conn, "player_stats_pitching",
            ["player_id", "season_id", "stat_period"] + list(PITCHING_DB_COLUMNS),
            pitching_rows
        )

    if projection_rows:
        counts["projections"] = bulk_insert(conn, "player_projections",
            ["player_id", "season_id", "projection_source", "projection_period", "player_type", "projections"],
            projection_rows
        )

    if valuation_rows:
        counts["valuations"] = bulk_insert(conn, "player_valuations",
            ["player_id", "season_id", "valuation_type", "primary_position", "tier", "total_z", "total_dollars"],
            valuation_rows
        )

        with conn.cursor() as cur:
            for player in data:
                vals = player.get("valuations")
                if not isinstance(vals, dict):
                    continue
                for val_type, val in vals.items():
                    if not val or "z_scores" not in val:
                        continue
                    cur.execute(
                        "SELECT id FROM player_valuations WHERE player_id = %s AND season_id = %s AND primary_position = %s AND valuation_type = %s",
                        (player["id_espn"], season_id, val.get("primary_position"), val_type)
                    )
                    result = cur.fetchone()
                    if not result:
                        continue
                    valuation_id = result[0]
                    dollar_values = val.get("dollar_values") or {}
                    for stat_cat, z_score in val["z_scores"].items():
                        dollar_val = dollar_values.get(stat_cat)
                        valuation_detail_rows.append((valuation_id, stat_cat, z_score, dollar_val))

        if valuation_detail_rows:
            bulk_insert(conn, "player_valuation_details",
                ["valuation_id", "stat_category", "z_score", "dollar_value"],
                valuation_detail_rows
            )

    return counts
