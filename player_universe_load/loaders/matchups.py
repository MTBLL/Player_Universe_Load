#!/usr/bin/env python3
"""Load matchup/schedule data into the database."""

from typing import Any
from ..db import bulk_insert


def load_matchups(conn, data: dict[str, Any]) -> int:
    """Load matchups from schedule data."""
    matchup_rows = []

    for matchup in data.get("matchups", []):
        matchup_rows.append((
            matchup["matchup_id"],
            data["league_id"],
            data["season_id"],
            matchup["period_id"],
            matchup.get("is_playoff", False),
            matchup.get("is_bye_week", False),
            matchup.get("team1_id"),
            matchup.get("team1_score"),
            matchup.get("team2_id"),
            matchup.get("team2_score"),
            matchup.get("winner_id"),
        ))

    return bulk_insert(conn, "matchups",
        ["matchup_id", "league_id", "season_id", "period_id", "is_playoff",
         "is_bye_week", "team1_id", "team1_score", "team2_id", "team2_score", "winner_id"],
        matchup_rows
    )
