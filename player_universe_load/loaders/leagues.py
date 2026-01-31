#!/usr/bin/env python3
"""Load league data into the database."""

from typing import Any
from ..db import bulk_insert, json_serialize


def load_league(conn, data: dict[str, Any]) -> dict[str, int]:
    """Load league summary and scoring categories."""
    counts = {"leagues": 0, "scoring_categories": 0}

    # Insert league
    league_row = (
        data["league_id"],
        data["season_id"],
        data.get("scoring_period_id"),
        data.get("num_teams"),
        data.get("acquisition_budget"),
        data.get("draft_auction_budget"),
        json_serialize(data.get("roster_settings")),
    )

    counts["leagues"] = bulk_insert(conn, "leagues",
        ["league_id", "season_id", "scoring_period_id", "num_teams",
         "acquisition_budget", "draft_auction_budget", "roster_settings"],
        [league_row]
    )

    # Insert scoring categories
    scoring_rows = []
    if "scoring_categories" in data:
        for stat_type, categories in data["scoring_categories"].items():
            for idx, cat in enumerate(categories):
                scoring_rows.append((
                    data["league_id"],
                    stat_type,
                    cat["stat_id"],
                    cat["name"],
                    cat.get("is_reverse", False),
                    idx,
                ))

    if scoring_rows:
        counts["scoring_categories"] = bulk_insert(conn, "league_scoring_categories",
            ["league_id", "stat_type", "stat_id", "stat_name", "is_reverse", "sort_order"],
            scoring_rows
        )

    return counts
