#!/usr/bin/env python3
"""Load matchup/schedule data into the database."""

from typing import Any
from ..db import bulk_insert


def load_matchups(conn, data: dict[str, Any]) -> dict[str, int]:
    """Load matchups and their per-category result breakdowns.

    Returns counts for both the matchups rows and the child
    matchup_categories rows.
    """
    matchup_rows = []
    category_rows = []

    for matchup in data.get("matchups", []):
        matchup_id = matchup["matchup_id"]
        matchup_rows.append((
            matchup_id,
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

        if matchup.get("is_bye_week"):
            # Bye weeks carry no category contest. Emit one sentinel row so
            # every matchup is represented in matchup_categories — downstream
            # joins/aggregations never silently miss a bye matchup.
            category_rows.append(
                (matchup_id, matchup.get("team1_id"), "BYE", None, "BYE")
            )
            continue

        # Played matchups carry team1_categories / team2_categories arrays;
        # future unplayed matchups carry neither, so emit no category rows.
        for side in ("team1", "team2"):
            team_id = matchup.get(f"{side}_id")
            for cat in matchup.get(f"{side}_categories", []):
                category_rows.append((
                    matchup_id,
                    team_id,
                    cat["category"],
                    cat.get("value"),
                    cat.get("result"),
                ))

    counts = {
        "matchups": bulk_insert(conn, "matchups",
            ["matchup_id", "league_id", "season_id", "period_id", "is_playoff",
             "is_bye_week", "team1_id", "team1_score", "team2_id",
             "team2_score", "winner_id"],
            matchup_rows
        ),
        "matchup_categories": bulk_insert(conn, "matchup_categories",
            ["matchup_id", "team_id", "category", "value", "result"],
            category_rows
        ),
    }
    return counts
