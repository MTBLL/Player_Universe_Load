#!/usr/bin/env python3
"""Load per-position auction-pricing aggregates from <scenario>/position_summary.csv.

Each of the 5 valuation scenarios (preseason/updated/ros/synthetic/current)
emits a position_summary.csv with one row per position. Hitter columns are
populated for hitter positions (C/1B/2B/3B/SS/OF/UTIL), pitcher columns for
SP/RP. Empty string cells are treated as NULL.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..db import bulk_insert


VALUATION_SCENARIOS = ("preseason", "updated", "ros", "synthetic", "current")

# Mapping: CSV column -> DB column. Identical for most, but quoted-slash names
# stay as their original CSV header (the bulk_insert quoter handles them).
_CSV_COLUMNS = (
    "rostered_count",
    "replacement_tier_count",
    "total_budget",
    "budget_R", "budget_HR", "budget_RBI", "budget_SBN", "budget_OBP", "budget_SLG",
    "pool_total_z_R", "pool_total_z_HR", "pool_total_z_RBI",
    "pool_total_z_SBN", "pool_total_z_OBP", "pool_total_z_SLG",
    "dollars_per_z_R", "dollars_per_z_HR", "dollars_per_z_RBI",
    "dollars_per_z_SBN", "dollars_per_z_OBP", "dollars_per_z_SLG",
    "replacement_baseline_R", "replacement_baseline_HR",
    "replacement_baseline_RBI", "replacement_baseline_SBN",
    "replacement_baseline_OBP", "replacement_baseline_SLG",
    "budget_IP", "budget_ERA", "budget_WHIP", "budget_K/9", "budget_QS",
    "pool_total_z_IP", "pool_total_z_ERA", "pool_total_z_WHIP",
    "pool_total_z_K/9", "pool_total_z_QS",
    "dollars_per_z_IP", "dollars_per_z_ERA", "dollars_per_z_WHIP",
    "dollars_per_z_K/9", "dollars_per_z_QS",
    "replacement_baseline_ERA", "replacement_baseline_WHIP",
    "replacement_baseline_QS", "replacement_baseline_K/9",
    "replacement_baseline_IP",
    "budget_SVHD", "pool_total_z_SVHD", "dollars_per_z_SVHD",
    "replacement_baseline_SVHD",
)

_INTEGER_COLUMNS = {"rostered_count", "replacement_tier_count"}


def _parse_cell(col: str, raw: str) -> Any:
    """Convert CSV cell to typed Python value; empty string -> None."""
    if raw == "" or raw is None:
        return None
    if col in _INTEGER_COLUMNS:
        return int(raw)
    return float(raw)


def load_position_summary(conn, scenario_dir: Path, valuation_type: str) -> dict[str, int]:
    """Load one scenario's position_summary.csv into the position_summary table.

    Returns {"position_summary": <inserted_count>}. Missing CSV is a no-op
    rather than an error so partial scenario sets (e.g. only preseason
    present in CI fixtures) don't fail the whole load.
    """
    counts = {"position_summary": 0}
    csv_file = scenario_dir / "position_summary.csv"
    if not csv_file.exists():
        return counts

    db_columns = ["position", "role", "valuation_type"] + list(_CSV_COLUMNS)
    rows: list[tuple] = []
    with csv_file.open(newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            row = (
                r["position"],
                r["role"],
                valuation_type,
            ) + tuple(_parse_cell(c, r.get(c, "")) for c in _CSV_COLUMNS)
            rows.append(row)

    if rows:
        counts["position_summary"] = bulk_insert(
            conn, "position_summary", db_columns, rows
        )
    return counts


def load_all_position_summaries(conn, load_dir: Path) -> dict[str, int]:
    """Iterate the 5 valuation scenarios under load_dir and aggregate counts."""
    total = {"position_summary": 0}
    for scenario in VALUATION_SCENARIOS:
        scenario_dir = load_dir / scenario
        if not scenario_dir.exists():
            continue
        counts = load_position_summary(conn, scenario_dir, scenario)
        total["position_summary"] += counts["position_summary"]
    return total
