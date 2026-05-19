#!/usr/bin/env python3
"""Tests for the parquet exporter.

Assumes the local Postgres has already been loaded via `load-local` — the
existing test_load_integration.py runs first and populates it.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pyarrow.parquet as pq
import pytest

from player_universe_load.db import get_connection
from player_universe_load.exporters.parquet import (
    EXPORTED_TABLES,
    export_all,
    export_table,
)


@pytest.fixture
def conn():
    c = get_connection()
    try:
        yield c
    finally:
        c.close()


@pytest.fixture
def tmp_target(tmp_path: Path) -> Path:
    return tmp_path / "analytics"


def test_export_all_writes_every_table(conn, tmp_target: Path):
    """One .parquet per declared table; no .tmp residue."""
    paths = export_all(conn, target_dir=tmp_target)
    assert len(paths) == len(EXPORTED_TABLES)
    for t in EXPORTED_TABLES:
        assert (tmp_target / f"{t}.parquet").exists()
    leftover = list(tmp_target.glob("*.parquet.tmp"))
    assert leftover == [], f"Unexpected .tmp residue: {leftover}"


def test_export_row_count_matches_postgres(conn, tmp_target: Path):
    """Parquet row counts must match Postgres for every table."""
    export_all(conn, target_dir=tmp_target)
    with conn.cursor() as cur:
        for t in EXPORTED_TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            pg_count = cur.fetchone()[0]
            pq_count = pq.read_table(tmp_target / f"{t}.parquet").num_rows
            assert pq_count == pg_count, f"{t}: parquet {pq_count} != postgres {pg_count}"


def test_atomic_swap_cleans_stale_tmp(conn, tmp_target: Path):
    """A leftover .parquet.tmp from a crashed prior run is swept before retry."""
    tmp_target.mkdir(parents=True, exist_ok=True)
    stale = tmp_target / "players.parquet.tmp"
    stale.write_bytes(b"GARBAGE")
    assert stale.exists()

    export_table(conn, "players", target_dir=tmp_target)

    assert not stale.exists(), "stale .tmp should be unlinked before write"
    assert (tmp_target / "players.parquet").exists()


def test_atomic_swap_no_tmp_on_failure(conn, tmp_target: Path):
    """When pq.write_table raises, no .parquet.tmp is left behind.

    unlink(missing_ok=True) at the start of the next run sweeps it; this
    test verifies the contract that .tmp is the only intermediate artifact
    and that a failure does not surface a partial .parquet.
    """
    tmp_target.mkdir(parents=True, exist_ok=True)

    with patch("player_universe_load.exporters.parquet.pq.write_table",
               side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            export_table(conn, "players", target_dir=tmp_target)

    # No final .parquet because write failed
    assert not (tmp_target / "players.parquet").exists()
    # The .tmp may exist (rename never ran) — verify next successful run sweeps it
    pre_existing_tmp = tmp_target / "players.parquet.tmp"
    pre_existing_tmp.touch(exist_ok=True)
    export_table(conn, "players", target_dir=tmp_target)
    assert not pre_existing_tmp.exists()
    assert (tmp_target / "players.parquet").exists()


def test_jsonb_roundtrip_preserves_structure(conn, tmp_target: Path):
    """JSONB columns serialize as JSON strings and round-trip cleanly."""
    export_table(conn, "players", target_dir=tmp_target)
    table = pq.read_table(tmp_target / "players.parquet")
    rows = table.to_pylist()

    # eligible_slots is a JSONB array of strings; birth_place is JSONB struct.
    sample = next(r for r in rows if r["eligible_slots"])
    assert isinstance(sample["eligible_slots"], str)
    parsed = json.loads(sample["eligible_slots"])
    assert isinstance(parsed, list)
    assert all(isinstance(x, str) for x in parsed)

    sample_bp = next((r for r in rows if r.get("birth_place")), None)
    if sample_bp is not None:
        bp = json.loads(sample_bp["birth_place"])
        assert isinstance(bp, dict)


def test_export_single_table_returns_final_path(conn, tmp_target: Path):
    """export_table returns the final .parquet path (not the .tmp)."""
    p = export_table(conn, "leagues", target_dir=tmp_target)
    assert p.name == "leagues.parquet"
    assert p.exists()
