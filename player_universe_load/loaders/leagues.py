#!/usr/bin/env python3
"""Load league data into the database."""

from typing import Any
from ..db import bulk_insert, json_serialize


def load_league(conn, data: dict[str, Any]) -> dict[str, int]:
    """Load league summary and scoring categories."""
    counts = {"leagues": 0, "scoring_categories": 0}

    # Games-started limits (pitcher start-cap rule). Absent upstream for
    # leagues with no start cap; `or {}` lets every .get() below fall through
    # to None so the league still loads.
    gsl = data.get("games_started_limits") or {}

    # Insert league
    league_row = (
        data["league_id"],
        data["season_id"],
        data.get("league_name"),
        data.get("scoring_period_id"),
        data.get("num_teams"),
        data.get("acquisition_budget"),
        data.get("draft_auction_budget"),
        json_serialize(data.get("roster_settings")),
        gsl.get("stat_id"),
        gsl.get("min"),
        gsl.get("max_per_scoring_period"),
        gsl.get("max_per_matchup"),
    )

    counts["leagues"] = bulk_insert(conn, "leagues",
        ["league_id", "season_id", "league_name", "scoring_period_id", "num_teams",
         "acquisition_budget", "draft_auction_budget", "roster_settings",
         "gsl_stat_id", "gsl_min", "gsl_max_per_scoring_period",
         "gsl_max_per_matchup"],
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
