#!/usr/bin/env python3
"""Targeted unit tests to push coverage to 100%.

These exercise error paths, edge cases, and pure-function helpers that the
integration tests don't hit. Most piggyback on the already-loaded local DB.
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from player_universe_load import db, __main__ as main_mod
from player_universe_load import cli, verification
from player_universe_load.exporters import parquet as parquet_mod
from player_universe_load.validation import schema_validator


# -------------------- db.py --------------------


def test_get_connection_missing_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL not found"):
        db.get_connection()


def test_get_connection_bad_url(monkeypatch, capsys):
    """Hits the connection-failure print + raise branch (db.py:37-39)."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://nope:nope@127.0.0.1:1/nodb")
    with pytest.raises(Exception):
        db.get_connection()
    assert "Connection failed" in capsys.readouterr().out


def test_bulk_insert_empty_rows():
    conn = db.get_connection()
    try:
        assert db.bulk_insert(conn, "players", ["id_espn"], []) == 0
    finally:
        conn.close()


def test_get_table_columns_known_and_unknown():
    conn = db.get_connection()
    try:
        cols = db.get_table_columns(conn, "players")
        assert "id_espn" in cols and "name" in cols
        assert db.get_table_columns(conn, "no_such_table_xyz") == set()
    finally:
        conn.close()


def test_validate_schema_missing_and_extra():
    conn = db.get_connection()
    try:
        is_valid, missing, extra = db.validate_schema(
            conn, "players", ["id_espn", "nonexistent_col"]
        )
        assert not is_valid
        assert "nonexistent_col" in missing
        assert "id" not in extra
        assert "created_at" not in extra
        assert "updated_at" not in extra
    finally:
        conn.close()


def test_json_serialize():
    assert db.json_serialize(None) is None
    assert db.json_serialize({"a": 1}) == '{"a": 1}'


# -------------------- exporters/parquet.py --------------------


def test_table_columns_raises_on_unknown_table():
    conn = db.get_connection()
    try:
        with pytest.raises(RuntimeError, match="not found in information_schema"):
            parquet_mod._table_columns(conn, "no_such_table_xyz")
    finally:
        conn.close()


def test_export_table_empty_table_preserves_types(tmp_path: Path):
    """P2: empty parquet must preserve real Arrow types, not collapse to null.

    Builds a temp table with several Postgres types, exports it empty, then
    asserts the read-back parquet schema carries int/decimal/string/bool/
    timestamp — not pyarrow null. NUMERIC maps to decimal128(18, 3) for
    lossless storage of stat values at thousandths precision.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TEMP TABLE _typed_empty_probe ("
                "  id INTEGER, "
                "  name TEXT, "
                "  rate NUMERIC, "
                "  is_active BOOLEAN, "
                "  payload JSONB, "
                "  created_at TIMESTAMP"
                ")"
            )
            conn.commit()
        path = parquet_mod.export_table(conn, "_typed_empty_probe", target_dir=tmp_path)
        t = pq.read_table(path)
        assert t.num_rows == 0
        schema = {f.name: f.type for f in t.schema}
        assert schema["id"] == pa.int32()
        assert schema["name"] == pa.string()
        assert schema["rate"] == pa.decimal128(18, 3)
        assert schema["is_active"] == pa.bool_()
        assert schema["payload"] == pa.string()  # JSONB encoded as string
        assert pa.types.is_timestamp(schema["created_at"])
    finally:
        conn.close()


def test_export_table_numeric_quantized_and_typed(tmp_path: Path):
    """Round-trip a non-empty NUMERIC column. Verify decimal128(18, 3) +
    ROUND_HALF_UP applied to values that would otherwise lose precision.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE _numeric_probe (id INTEGER, era NUMERIC)")
            # Use values that exercise ROUND_HALF_UP behavior
            cur.execute(
                "INSERT INTO _numeric_probe VALUES "
                "(1, 4.5675), "  # half-up -> 4.568
                "(2, 4.5674), "  # half-down -> 4.567
                "(3, 0.27815), "  # half-up tail -> 0.278
                "(4, NULL)"
            )
            conn.commit()
        path = parquet_mod.export_table(conn, "_numeric_probe", target_dir=tmp_path)
        t = pq.read_table(path)
        assert t.schema.field("era").type == pa.decimal128(18, 3)
        # to_pylist returns Decimal at the declared scale
        eras = t.column("era").to_pylist()
        assert eras[0] == Decimal("4.568")
        assert eras[1] == Decimal("4.567")
        assert eras[2] == Decimal("0.278")
        assert eras[3] is None
    finally:
        conn.close()


def test_arrow_schema_unknown_pg_type_falls_back_to_string(tmp_path: Path):
    """Unknown Postgres type maps to pa.string() — defensive fallback."""
    import pyarrow as pa

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE _unknown_probe (label inet)")
            conn.commit()
        schema = parquet_mod._arrow_schema_for(conn, "_unknown_probe")
        assert schema.field("label").type == pa.string()
    finally:
        conn.close()


def test_export_all_propagates_error(tmp_path: Path):
    conn = db.get_connection()
    try:
        with patch.object(parquet_mod, "EXPORTED_TABLES", ("no_such_table_xyz",)):
            with pytest.raises(RuntimeError):
                parquet_mod.export_all(conn, target_dir=tmp_path)
    finally:
        conn.close()


def test_sanitize_decimals_handles_infinity_and_quantizes_finite():
    """Non-finite -> None. Finite -> quantize to thousandths, ROUND_HALF_UP."""
    rows = [
        {"era": Decimal("4.50"), "whip": Decimal("Infinity")},
        {"era": Decimal("-Infinity"), "whip": Decimal("NaN")},
        {"era": None, "whip": Decimal("1.20")},
        # Truncation + rounding behavior
        {"era": Decimal("4.5675"), "whip": Decimal("4.5674")},  # half-up: .5675->.568, .5674->.567
        {"era": Decimal("0.2785"), "whip": Decimal("0.2775")},  # half-up: .2785->.279, .2775->.278
        {"era": Decimal("-4.5675"), "whip": Decimal("-0.0005")},  # negative half-up: -.5675->-.568
    ]
    parquet_mod._sanitize_decimals(rows)
    # Non-finite sanitized
    assert rows[0]["era"] == Decimal("4.500")  # quantized to scale 3
    assert rows[0]["whip"] is None
    assert rows[1]["era"] is None
    assert rows[1]["whip"] is None
    assert rows[2]["whip"] == Decimal("1.200")
    # Half-up rounding (not banker's)
    assert rows[3]["era"] == Decimal("4.568")
    assert rows[3]["whip"] == Decimal("4.567")
    assert rows[4]["era"] == Decimal("0.279")
    assert rows[4]["whip"] == Decimal("0.278")
    assert rows[5]["era"] == Decimal("-4.568")
    assert rows[5]["whip"] == Decimal("-0.001")  # half-up on negative: -0.0005 -> -0.001


def test_stringify_jsonb_skips_already_string():
    rows = [
        {"j": {"a": 1}, "k": "v"},
        {"j": '{"prebaked": true}', "k": "v"},
        {"j": None, "k": "v"},
    ]
    parquet_mod._stringify_jsonb(rows, ["j"])
    assert rows[0]["j"] == '{"a": 1}'
    assert rows[1]["j"] == '{"prebaked": true}'
    assert rows[2]["j"] is None


def test_stringify_jsonb_no_cols_short_circuits():
    rows = [{"a": 1}]
    assert parquet_mod._stringify_jsonb(rows, []) is rows


# -------------------- validation/schema_validator.py --------------------


def test_validate_data_schema_pass(tmp_path: Path):
    fdir = tmp_path / "fix"
    fdir.mkdir()
    hitter = {
        "id_espn": 1,
        "name": "Test",
        "stats": {"espn": {"current_season": {"AB": 100, "AVG": 0.300}}},
    }
    pitcher = {
        "id_espn": 2,
        "name": "Pitch",
        "stats": {"espn": {"current_season": {"IP": 50, "ERA": 3.50}}},
    }
    (fdir / "hitters.json").write_text(json.dumps([hitter]))
    (fdir / "pitchers.json").write_text(json.dumps([pitcher]))

    conn = db.get_connection()
    try:
        assert schema_validator.validate_data_schema(conn, fdir) is True
    finally:
        conn.close()


def test_validate_data_schema_missing_files(tmp_path: Path):
    fdir = tmp_path / "empty"
    fdir.mkdir()
    conn = db.get_connection()
    try:
        assert schema_validator.validate_data_schema(conn, fdir) is True
    finally:
        conn.close()


def test_validate_data_schema_empty_data(tmp_path: Path):
    fdir = tmp_path / "empty_data"
    fdir.mkdir()
    (fdir / "hitters.json").write_text("[]")
    (fdir / "pitchers.json").write_text("[]")
    conn = db.get_connection()
    try:
        assert schema_validator.validate_data_schema(conn, fdir) is True
    finally:
        conn.close()


def test_validate_data_schema_mismatch_raises_with_extra_cols(tmp_path: Path, capsys):
    """Force missing + extra reporting paths inside validate_data_schema."""
    fdir = tmp_path / "mm"
    fdir.mkdir()
    hitter = {
        "id_espn": 1,
        "name": "x",
        "stats": {"espn": {"current_season": {"AB": 1}}},
    }
    pitcher = {
        "id_espn": 2,
        "name": "p",
        "stats": {"espn": {"current_season": {"IP": 1}}},
    }
    (fdir / "hitters.json").write_text(json.dumps([hitter]))
    (fdir / "pitchers.json").write_text(json.dumps([pitcher]))
    conn = db.get_connection()
    try:
        # Patch the player column list so validation finds missing cols (lines 78, 100, 106-122)
        with patch.object(schema_validator, "PLAYER_COLUMNS", ["nonexistent_col_zz"]):
            with patch.object(schema_validator, "BATTING_STAT_COLUMNS", ["nonexistent_batting_zz"]):
                with patch.object(schema_validator, "PITCHING_STAT_COLUMNS", ["nonexistent_pitching_zz"]):
                    with pytest.raises(SystemExit):
                        schema_validator.validate_data_schema(conn, fdir)
        # Verify the "extra in DB" + "missing in data" prints fired
        out = capsys.readouterr().out
        assert "SCHEMA MISMATCH" in out
        assert "Missing in DB" in out
        assert "In DB but not in data" in out
    finally:
        conn.close()


def test_warn_unknown_keys_flags_drift(tmp_path: Path, capsys):
    """_warn_unknown_keys surfaces upstream keys no loader consumes.

    Fixtures carry no drift, so CI never exercises the warning branches —
    this test makes them deterministic.
    """
    fdir = tmp_path / "drift"
    fdir.mkdir()
    (fdir / "league_10998_summary.json").write_text(
        json.dumps(
            {"league_id": 10998, "season_id": 2026, "brand_new_field": "x"}
        )
    )
    (fdir / "league_10998_schedule.json").write_text(
        json.dumps(
            {
                "league_id": 10998,
                "season_id": 2026,
                "matchups": [
                    {"matchup_id": 1, "period_id": 1, "surprise_key": True}
                ],
            }
        )
    )
    schema_validator._warn_unknown_keys(fdir)
    out = capsys.readouterr().out
    assert "brand_new_field" in out
    assert "surprise_key" in out


def test_warn_unknown_keys_silent_when_clean(tmp_path: Path, capsys):
    """No warning when every key is handled."""
    fdir = tmp_path / "clean"
    fdir.mkdir()
    (fdir / "league_10998_summary.json").write_text(
        json.dumps({"league_id": 10998, "season_id": 2026})
    )
    schema_validator._warn_unknown_keys(fdir)
    assert "unhandled" not in capsys.readouterr().out


# -------------------- loaders/matchups.py --------------------


def test_load_matchups_flattens_categories_and_bye_placeholder():
    """load_matchups flattens teamN_categories into child rows and emits a
    bye sentinel. Fixtures lack team*_categories, so CI never hits the
    category-append line without this test."""
    from player_universe_load.loaders.matchups import load_matchups

    schedule = {
        "league_id": 10998,
        "season_id": 2026,
        "matchups": [
            {
                "matchup_id": 90001,
                "period_id": 1,
                "is_bye_week": False,
                "team1_id": 1,
                "team1_score": "2-1-0",
                "team2_id": 7,
                "team2_score": "1-2-0",
                "winner_id": 1,
                "team1_categories": [
                    {"category": "HR", "value": 9.0, "result": "WIN"},
                    {"category": "ERA", "value": 3.1, "result": "LOSS"},
                ],
                "team2_categories": [
                    {"category": "HR", "value": 4.0, "result": "LOSS"},
                ],
            },
            {
                "matchup_id": 90002,
                "period_id": 1,
                "is_bye_week": True,
                "team1_id": 8,
                "team1_score": "0-0-0",
            },
        ],
    }
    counts = load_matchups(MagicMock(), schedule)
    assert counts["matchups"] == 2
    # 2 team1 + 1 team2 category rows, plus 1 bye sentinel row.
    assert counts["matchup_categories"] == 4


# -------------------- __main__.py --------------------


def test_main_no_args(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["player-universe-load"])
    rc = main_mod.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "load-and-sync" in out


def test_main_with_args_delegates(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["player-universe-load", "verify"])
    with patch("player_universe_load.cli.main", return_value=0) as cli_main:
        assert main_mod.main() == 0
        cli_main.assert_called_once()


def test_load_all_uses_fixtures_when_pipeline_dirs_missing(tmp_path, monkeypatch):
    """Force use_pipeline=False path (lines 38-39, 54-56)."""
    nonexistent = tmp_path / "does_not_exist"  # never created
    monkeypatch.setattr(main_mod, "TRANSFORM_DIR", nonexistent)
    monkeypatch.setattr(main_mod, "LOAD_DIR", nonexistent)
    # Point fixtures at the real repo fixtures so the load actually succeeds
    monkeypatch.setattr(main_mod, "FIXTURES_DIR", Path("tests/fixtures"))
    main_mod.load_all()


def test_load_all_missing_files_emits_warnings(tmp_path: Path, monkeypatch, capsys):
    """All inputs absent -> each `file not found` warning fires."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(main_mod, "TRANSFORM_DIR", empty)
    monkeypatch.setattr(main_mod, "LOAD_DIR", empty)
    monkeypatch.setattr(main_mod, "FIXTURES_DIR", empty)
    main_mod.load_all()
    out = capsys.readouterr().out
    assert "Hitters file not found" in out
    assert "Pitchers file not found" in out
    assert "League file not found" in out
    assert "No team files found" in out
    assert "Schedule file not found" in out


def test_load_all_error_path_rolls_back(monkeypatch):
    """Force init_schema to raise -> rollback + re-raise."""
    def boom(_conn):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(main_mod, "init_schema", boom)
    with pytest.raises(RuntimeError, match="kaboom"):
        main_mod.load_all()


# -------------------- loaders/teams.py --------------------


def test_load_team_handles_bad_acquisition_date_and_none_slot():
    """Cover lines 66 (bad date except) + 73-74 (None player skip).

    Self-contained: inserts a player + league + team directly so this
    test does not depend on prior test state.
    """
    from player_universe_load.loaders.teams import load_team_roster

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO players (id_espn, name) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                (888001, "Coverage Player"),
            )
            cur.execute(
                'INSERT INTO leagues (league_id, season_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                (98765, 2026),
            )
            cur.execute(
                'INSERT INTO teams (team_id, league_id, season_id, team_name) '
                'VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING',
                (98765001, 98765, 2026, "Cov Team"),
            )
            conn.commit()

        data = {
            "team_id": 98765001,
            "league_id": 98765,
            "season_id": 2026,
            "team_name": "Cov Team",
            "team_abbrev": "CV",
            "team_logo": None,
            "primary_owner": None,
            "owners": [],
            "record": {},
            "transactions": {},
            "bench": [
                {"player_id": 888001, "acquisition_date": "not-a-date"},  # except branch
                None,  # `if not player: continue` branch
            ],
        }
        counts = load_team_roster(conn, data)
        assert counts["roster_slots"] >= 1
    finally:
        conn.close()


# -------------------- loaders/players.py --------------------


def test_infer_player_type_explicit_markers():
    from player_universe_load.loaders.players import _infer_player_type

    assert _infer_player_type({"player_type": "batter"}) == "batter"
    assert _infer_player_type({"player_type": "hitter"}) == "batter"
    assert _infer_player_type({"player_type": "Batter"}) == "batter"
    assert _infer_player_type({"player_type": "pitcher"}) == "pitcher"


def test_infer_player_type_from_stat_keys():
    from player_universe_load.loaders.players import _infer_player_type

    # Marker absent — must sniff stat keys
    batter = {"stats": {"espn": {"current_season": {"AB": 100, "AVG": 0.250}}}}
    pitcher = {"stats": {"espn": {"current_season": {"IP": 50, "ERA": 3.0}}}}
    assert _infer_player_type(batter) == "batter"
    assert _infer_player_type(pitcher) == "pitcher"

    # ESPN B_BB / P_BB prefixed keys
    assert _infer_player_type({"stats": {"espn": {"current_season": {"B_BB": 30}}}}) == "batter"
    assert _infer_player_type({"stats": {"espn": {"current_season": {"P_BB": 30}}}}) == "pitcher"

    # Fangraphs projections only
    fg_pitcher = {"stats": {"fangraphs": {"projections": {"IP": 180, "ERA": 4.0}}}}
    assert _infer_player_type(fg_pitcher) == "pitcher"

    # Savant tabular only
    sv_batter = {"stats": {"savant": {"all": {"AVG": 0.3, "BB_pct": 10.0, "B_SO": 50}}}}
    assert _infer_player_type(sv_batter) == "batter"

    # No stats at all -> default pitcher (last resort)
    assert _infer_player_type({}) == "pitcher"
    assert _infer_player_type({"player_type": "unknown"}) == "pitcher"


def test_load_players_routes_hitter_payload_without_marker():
    """Regression P1: hitter feed without player_type marker must land in batting."""
    from player_universe_load.loaders.players import load_players

    conn = db.get_connection()
    try:
        data = [
            {
                "id_espn": 999999030,
                "name": "Marker Absent Hitter",
                # NO player_type field
                "stats": {
                    "espn": {
                        "current_season": {
                            "AB": 400, "H": 110, "AVG": 0.275,
                            "HR": 20, "R": 60, "RBI": 70,
                        }
                    }
                },
            }
        ]
        counts = load_players(conn, data, season_id=2026)
        assert counts["batting"] >= 1
        assert counts["pitching"] == 0
    finally:
        conn.close()


def test_load_position_summary_parses_csv(tmp_path: Path):
    """One scenario dir -> one row per CSV record, with mixed null/int/float."""
    from player_universe_load.loaders.position_summary import load_position_summary

    scenario_dir = tmp_path / "preseason"
    scenario_dir.mkdir()
    csv = scenario_dir / "position_summary.csv"
    # Reduced column set is fine — extra cols in real CSV map to NULL when missing,
    # so a minimal header still exercises the integer + float + empty-string paths.
    csv.write_text(
        "position,role,rostered_count,replacement_tier_count,total_budget,"
        "budget_R,budget_HR,budget_RBI,budget_SBN,budget_OBP,budget_SLG\n"
        "C,HITTER,11,3,218.4,27.13,31.71,30.64,2.78,60.91,65.24\n"
        # Pitcher row with empty hitter cols
        "SP,PITCHER,12,5,,,,,,,\n"
    )
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM position_summary WHERE valuation_type='_tst_preseason'"
            )
            conn.commit()
        counts = load_position_summary(conn, scenario_dir, "_tst_preseason")
        assert counts["position_summary"] == 2
        with conn.cursor() as cur:
            cur.execute(
                'SELECT position, role, rostered_count, total_budget, "budget_R" '
                "FROM position_summary WHERE valuation_type='_tst_preseason' "
                "ORDER BY position"
            )
            rows = cur.fetchall()
        # C/HITTER: full values
        assert rows[0][0] == "C" and rows[0][1] == "HITTER"
        assert rows[0][2] == 11
        assert float(rows[0][3]) == 218.4
        assert float(rows[0][4]) == 27.13
        # SP/PITCHER: empty cols -> NULL
        assert rows[1][0] == "SP" and rows[1][1] == "PITCHER"
        assert rows[1][3] is None and rows[1][4] is None
    finally:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM position_summary WHERE valuation_type='_tst_preseason'"
            )
            conn.commit()
        conn.close()


def test_load_position_summary_missing_csv_is_noop(tmp_path: Path):
    from player_universe_load.loaders.position_summary import load_position_summary

    scenario_dir = tmp_path / "preseason"
    scenario_dir.mkdir()
    conn = db.get_connection()
    try:
        counts = load_position_summary(conn, scenario_dir, "preseason")
        assert counts["position_summary"] == 0
    finally:
        conn.close()


def test_load_all_position_summaries_skips_missing_scenarios(tmp_path: Path):
    """Only some of the 5 scenarios present -> total counts sum what we have."""
    from player_universe_load.loaders.position_summary import (
        load_all_position_summaries,
    )

    load_dir = tmp_path / "load"
    load_dir.mkdir()
    # Only preseason + current present; ros, updated, synthetic absent.
    for s in ("preseason", "current"):
        d = load_dir / s
        d.mkdir()
        (d / "position_summary.csv").write_text(
            "position,role,rostered_count,replacement_tier_count,total_budget\n"
            "OF,HITTER,30,5,400.0\n"
        )
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM position_summary "
                "WHERE valuation_type IN ('preseason','current') "
                "AND position = '__tst_OF'"
            )
            conn.commit()

        # We're going to insert real rows; rather than dirty global state,
        # rewrite our CSV positions to a sentinel value
        for s in ("preseason", "current"):
            (load_dir / s / "position_summary.csv").write_text(
                "position,role,rostered_count,replacement_tier_count,total_budget\n"
                "__tst_OF,HITTER,30,5,400.0\n"
            )

        counts = load_all_position_summaries(conn, load_dir)
        assert counts["position_summary"] == 2  # 2 scenarios × 1 row each
    finally:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM position_summary WHERE position = '__tst_OF'"
            )
            conn.commit()
        conn.close()


def test_load_players_handles_no_stats_no_valuations():
    from player_universe_load.loaders.players import load_players

    conn = db.get_connection()
    try:
        data = [
            {
                "id_espn": 999999001,
                "name": "Empty Slate",
                "player_type": "batter",
                "stats": {},
                "valuations": None,
            },
            {
                "id_espn": 999999002,
                "name": "Empty Vals",
                "player_type": "pitcher",
                "stats": {"espn": {}, "savant": {}, "fangraphs": {}},
                "valuations": {"preseason": None, "current": {}},
            },
        ]
        counts = load_players(conn, data, season_id=2026)
        assert counts["players"] == 2
    finally:
        conn.close()


def test_load_players_valuations_non_dict_skip():
    """Cover players.py:390 — second-pass loop skips when valuations is not a dict."""
    from player_universe_load.loaders.players import load_players

    conn = db.get_connection()
    try:
        data = [
            {
                "id_espn": 999999010,
                "name": "Has Vals",
                "player_type": "batter",
                "stats": {},
                "valuations": {
                    "preseason": {
                        "primary_position": "OF",
                        "tier": "ROSTERED",
                        "total_z": 0.0,
                        "total_dollars": 0.0,
                        "z_scores": {"R": 1.0},
                        "dollar_values": {"R": 1.0},
                    },
                    # No z_scores -> hits line 390 continue
                    "current": {
                        "primary_position": "OF",
                        "tier": "ROSTERED",
                        "total_z": 0.0,
                        "total_dollars": 0.0,
                    },
                },
            },
        ]
        counts = load_players(conn, data, season_id=2026)
        assert counts["valuations"] >= 1
    finally:
        conn.close()


def test_load_players_valuation_lookup_no_row_via_wrapping_conn():
    """Cover players.py:397 (lookup-miss `if not result: continue`).

    psycopg2 connections don't allow attribute monkeypatching, so wrap the
    connection in a thin class whose cursor returns a wrapper that rewrites
    the valuation-lookup SELECT to a guaranteed-empty result.
    """
    from player_universe_load.loaders.players import load_players

    real_conn = db.get_connection()
    try:
        class WrappedCursor:
            def __init__(self, real):
                self._real = real

            def __enter__(self):
                self._real.__enter__()
                return self

            def __exit__(self, *a):
                return self._real.__exit__(*a)

            def execute(self, q, params=None):
                if "SELECT id FROM player_valuations" in q:
                    self._real.execute("SELECT 1 WHERE FALSE")
                else:
                    if params is None:
                        self._real.execute(q)
                    else:
                        self._real.execute(q, params)

            def fetchone(self):
                return self._real.fetchone()

            def fetchall(self):
                return self._real.fetchall()

            def executemany(self, q, rows):
                return self._real.executemany(q, rows)

        class WrappingConn:
            def __init__(self, real):
                self._real = real

            def cursor(self, *a, **kw):
                return WrappedCursor(self._real.cursor(*a, **kw))

            def commit(self):
                self._real.commit()

            def rollback(self):
                self._real.rollback()

            def close(self):
                self._real.close()

        wrapped = WrappingConn(real_conn)
        data = [
            {
                "id_espn": 999999020,
                "name": "Lookup Miss",
                "player_type": "batter",
                "stats": {},
                "valuations": {
                    "preseason": {
                        "primary_position": "OF",
                        "tier": "ROSTERED",
                        "total_z": 0.0,
                        "total_dollars": 0.0,
                        "z_scores": {"R": 1.0},
                        "dollar_values": {"R": 1.0},
                    },
                },
            }
        ]
        load_players(wrapped, data, season_id=2026)
    finally:
        real_conn.close()


# -------------------- cli.py --------------------


def test_cli_local_url_default(monkeypatch):
    monkeypatch.delenv("LOCAL_DATABASE_URL", raising=False)
    assert cli._local_url() == "postgresql://localhost/fantasy_baseball"


def test_cli_local_url_override(monkeypatch):
    monkeypatch.setenv("LOCAL_DATABASE_URL", "postgresql://x/y")
    assert cli._local_url() == "postgresql://x/y"


def test_cli_load_local_delegates(monkeypatch):
    with patch("player_universe_load.cli.load_all") as la:
        cli.load_local(year=2026)
        la.assert_called_once_with(year=2026)


def test_cli_export_parquets_runs(monkeypatch, tmp_path: Path):
    """Cover cli.export_parquets — uses real connection, mocked export_all."""
    with patch("player_universe_load.cli.export_all", return_value=[tmp_path / "a.parquet"]) as ea:
        cli.export_parquets()
        ea.assert_called_once()


def test_cli_sync_to_neon_missing_url(monkeypatch):
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit):
        cli.sync_to_neon()


def test_cli_sync_to_neon_happy_path(monkeypatch, tmp_path: Path):
    """Mock pg_dump + psql subprocess calls + the dump file lifecycle."""
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://u:p@host/db")
    dump_path = tmp_path / "fantasy_baseball_dump.sql"
    dump_path.write_text("-- fake dump\n")

    with patch("player_universe_load.cli.subprocess.run") as sub_run, \
         patch("player_universe_load.cli.os.path.getsize", return_value=1024 * 1024), \
         patch("player_universe_load.cli.os.remove") as rm, \
         patch("builtins.open", create=True) as op:
        sub_run.return_value = MagicMock(returncode=0, stderr="")
        op.return_value = MagicMock()
        cli.sync_to_neon()
        assert sub_run.call_count == 2  # pg_dump + psql
        rm.assert_called_once()


def test_cli_sync_to_neon_pg_dump_fails(monkeypatch):
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://u:p@host/db")
    with patch("player_universe_load.cli.subprocess.run") as sub_run, \
         patch("builtins.open", create=True):
        sub_run.return_value = MagicMock(returncode=1, stderr="boom")
        with pytest.raises(SystemExit):
            cli.sync_to_neon()


def test_cli_sync_to_neon_psql_fails(monkeypatch):
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://u:p@host/db")
    with patch("player_universe_load.cli.subprocess.run") as sub_run, \
         patch("player_universe_load.cli.os.path.getsize", return_value=1024), \
         patch("builtins.open", create=True):
        # First call (pg_dump) succeeds; second (psql) fails
        sub_run.side_effect = [
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=1, stderr="psql died"),
        ]
        with pytest.raises(SystemExit):
            cli.sync_to_neon()


def test_cli_sync_to_neon_no_at_in_url(monkeypatch, tmp_path: Path):
    """The NEON URL print branch when there's no `@`."""
    monkeypatch.setenv("NEON_DATABASE_URL", "weirdurl_noat")
    with patch("player_universe_load.cli.subprocess.run") as sub_run, \
         patch("player_universe_load.cli.os.path.getsize", return_value=1024), \
         patch("player_universe_load.cli.os.remove"), \
         patch("builtins.open", create=True):
        sub_run.return_value = MagicMock(returncode=0, stderr="")
        cli.sync_to_neon()


def test_cli_load_and_sync_orchestrates(monkeypatch):
    with patch("player_universe_load.cli.load_local") as ll, \
         patch("player_universe_load.cli.export_parquets") as ep, \
         patch("player_universe_load.cli.upload_parquets") as up, \
         patch("player_universe_load.cli.sync_to_neon") as sn:
        cli.load_and_sync(year=2026)
        ll.assert_called_once_with(year=2026)
        ep.assert_called_once()
        up.assert_called_once()
        sn.assert_called_once()


def test_cli_verify_delegates():
    with patch("player_universe_load.verification.verify_database") as vd:
        cli.verify()
        vd.assert_called_once()


def test_cli_main_each_command(monkeypatch):
    """Exercise each argparse branch."""
    for cmd, target in [
        ("load-and-sync", "player_universe_load.cli.load_and_sync"),
        ("load-local", "player_universe_load.cli.load_local"),
        ("sync-to-neon", "player_universe_load.cli.sync_to_neon"),
        ("export-parquets", "player_universe_load.cli.export_parquets"),
        ("upload-parquets", "player_universe_load.cli.upload_parquets"),
        ("parquet-and-sync", "player_universe_load.cli.parquet_and_sync"),
        ("verify-r2", "player_universe_load.cli.verify_r2"),
        ("verify", "player_universe_load.cli.verify"),
    ]:
        monkeypatch.setattr(sys, "argv", ["player-universe-load", cmd])
        with patch(target) as t:
            assert cli.main() == 0
            assert t.called


# -------------------- verification.py --------------------


def test_verify_database_local_only(monkeypatch, capsys):
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
    verification.verify_database()
    out = capsys.readouterr().out
    assert "Local PostgreSQL" in out
    assert "Skipping Neon verification" in out


def test_verify_database_with_neon(monkeypatch, capsys):
    """Point NEON to the same local URL so the Neon branch executes."""
    local_url = os.environ.get(
        "LOCAL_DATABASE_URL", "postgresql://localhost/fantasy_baseball"
    )
    monkeypatch.setenv("NEON_DATABASE_URL", local_url)
    verification.verify_database()
    out = capsys.readouterr().out
    assert "Neon PostgreSQL" in out


def test_verify_database_connection_failure(monkeypatch, capsys):
    monkeypatch.setenv("LOCAL_DATABASE_URL", "postgresql://nope:nope@127.0.0.1:1/nodb")
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
    verification.verify_database()
    out = capsys.readouterr().out
    assert "Failed to connect" in out


def test_verify_no_tables(monkeypatch, capsys):
    """Empty DB branch — fresh temp database with no schema."""
    # Connect to local DB, then patch the cursor's execute on "information_schema.tables"
    # to return empty. Simpler: patch the cursor's fetchall on the first query.
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
    real_conn = db.get_connection
    seen = {"first": True}

    class FakeCursor:
        def __init__(self):
            self.last_q = ""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def execute(self, q, params=None):
            self.last_q = q

        def fetchall(self):
            return []  # no tables

        def fetchone(self):
            return ["PostgreSQL Test"]

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    with patch("player_universe_load.verification.get_connection", return_value=FakeConn()):
        verification.verify_database()
    out = capsys.readouterr().out
    assert "No tables found" in out


def test_verify_empty_tables_branch(monkeypatch, capsys):
    """Tables exist but all have 0 rows."""
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)

    class FakeCursor:
        def __init__(self):
            self.last_q = ""
            self.call_i = 0

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def execute(self, q, params=None):
            self.last_q = q
            self.call_i += 1

        def fetchall(self):
            if "information_schema.tables" in self.last_q:
                return [("players",), ("teams",)]
            return []  # sample queries: no results

        def fetchone(self):
            if self.last_q.startswith("SELECT version"):
                return ["PostgreSQL Test"]
            if "COUNT" in self.last_q:
                return (0,)
            return ("PostgreSQL Test",)

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    with patch("player_universe_load.verification.get_connection", return_value=FakeConn()):
        verification.verify_database()
    out = capsys.readouterr().out
    assert "All tables are empty" in out


def test_verify_with_long_string_and_null_in_sample(monkeypatch, capsys):
    """Cover the truncate-long-string branch + None-formatting branch."""
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)

    class FakeCursor:
        def __init__(self):
            self.last_q = ""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def execute(self, q, params=None):
            self.last_q = q

        def fetchall(self):
            if "information_schema.tables" in self.last_q:
                return [("players",)]
            # Sample query result: long string + None + int + float
            return [("X" * 50, None, 5, 0.300)]

        def fetchone(self):
            if self.last_q.startswith("SELECT version"):
                return ["PostgreSQL Test"]
            if "COUNT" in self.last_q:
                return (10,)
            return None

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    with patch("player_universe_load.verification.get_connection", return_value=FakeConn()):
        verification.verify_database()
    out = capsys.readouterr().out
    # truncated long string shows "..."
    assert "..." in out
    # None formats as "--"
    assert "--" in out
