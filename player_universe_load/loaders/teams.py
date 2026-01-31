#!/usr/bin/env python3
"""Load team and roster data into the database."""

from typing import Any
from datetime import datetime
from ..db import bulk_insert, json_serialize


def load_team_roster(conn, data: dict[str, Any]) -> dict[str, int]:
    """Load team info and roster slots."""
    counts = {"teams": 0, "roster_slots": 0, "fantasy_assignments": 0}

    # Insert team
    record = data.get("record", {})
    transactions = data.get("transactions", {})

    team_row = (
        data["team_id"],
        data["league_id"],
        data["season_id"],
        data.get("team_name"),
        data.get("team_abbrev"),
        data.get("team_logo"),
        data.get("primary_owner"),
        json_serialize(data.get("owners")),
        record.get("wins", 0),
        record.get("losses", 0),
        record.get("ties", 0),
        record.get("percentage"),
        record.get("games_back"),
        transactions.get("budget_spent", 0),
        transactions.get("budget_remaining"),
        transactions.get("acquisitions", 0),
        transactions.get("drops", 0),
        transactions.get("trades", 0),
        transactions.get("waiver_rank"),
    )

    counts["teams"] = bulk_insert(conn, "teams",
        ["team_id", "league_id", "season_id", "team_name", "team_abbrev", "team_logo",
         "primary_owner", "owners", "wins", "losses", "ties", "win_percentage",
         "games_back", "budget_spent", "budget_remaining", "acquisitions",
         "drops", "trades", "waiver_rank"],
        [team_row]
    )

    # Roster slots and fantasy assignments
    roster_rows = []
    assignment_rows = []

    # Handle all position types
    position_fields = ["c", "first_base", "second_base", "third_base", "shortstop",
                      "util", "outfield", "sp", "rp", "bench", "injured_list"]

    for field in position_fields:
        if field not in data:
            continue

        players = data[field]
        # Some positions are lists, others are single players
        if not isinstance(players, list):
            players = [players] if players else []

        for player in players:
            if not player:
                continue

            # Roster slot
            acquisition_date = None
            if player.get("acquisition_date"):
                try:
                    acquisition_date = datetime.fromisoformat(player["acquisition_date"].replace("Z", "+00:00"))
                except:
                    pass

            roster_rows.append((
                data["team_id"],
                data["league_id"],
                data["season_id"],
                player["player_id"],
                player.get("lineup_slot", field.upper()),
                player.get("acquisition_type"),
                acquisition_date,
                player.get("keeper_value"),
            ))

            # Fantasy assignment
            assignment_rows.append((
                player["player_id"],
                data["league_id"],
                data["team_id"],
                data["season_id"],
                player.get("keeper_value"),  # Use keeper_value as draft_value for now
                None,  # draft_round
                None,  # draft_pick
            ))

    if roster_rows:
        counts["roster_slots"] = bulk_insert(conn, "roster_slots",
            ["team_id", "league_id", "season_id", "player_id", "lineup_slot",
             "acquisition_type", "acquisition_date", "keeper_value"],
            roster_rows
        )

    if assignment_rows:
        counts["fantasy_assignments"] = bulk_insert(conn, "player_fantasy_assignments",
            ["player_id", "league_id", "team_id", "season_id", "draft_value",
             "draft_round", "draft_pick"],
            assignment_rows
        )

    return counts
