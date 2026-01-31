#!/usr/bin/env python3
"""Integration tests for database loading."""

import pytest
from player_universe_load.db import get_connection
from player_universe_load.__main__ import load_all


def test_load_all_fixtures():
    """Load all fixtures and verify data was inserted."""
    # Run the full load
    load_all()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Test players loaded
            cur.execute("SELECT COUNT(*) FROM players")
            player_count = cur.fetchone()[0]
            assert player_count > 0, "Should have players loaded"
            print(f"✓ {player_count} players loaded")

            # Test batting stats loaded
            cur.execute("SELECT COUNT(*) FROM player_stats_batting")
            batting_count = cur.fetchone()[0]
            assert batting_count > 0, "Should have batting stats"
            print(f"✓ {batting_count} batting stat records loaded")

            # Test pitching stats loaded
            cur.execute("SELECT COUNT(*) FROM player_stats_pitching")
            pitching_count = cur.fetchone()[0]
            assert pitching_count > 0, "Should have pitching stats"
            print(f"✓ {pitching_count} pitching stat records loaded")

            # Test league loaded
            cur.execute("SELECT COUNT(*) FROM leagues")
            league_count = cur.fetchone()[0]
            assert league_count == 1, "Should have 1 league"
            print(f"✓ {league_count} league loaded")

            # Test scoring categories loaded
            cur.execute("SELECT COUNT(*) FROM league_scoring_categories")
            scoring_count = cur.fetchone()[0]
            assert scoring_count > 0, "Should have scoring categories"
            print(f"✓ {scoring_count} scoring categories loaded")

            # Test teams loaded
            cur.execute("SELECT COUNT(*) FROM teams")
            team_count = cur.fetchone()[0]
            assert team_count > 0, "Should have teams"
            print(f"✓ {team_count} teams loaded")

            # Test matchups loaded
            cur.execute("SELECT COUNT(*) FROM matchups")
            matchup_count = cur.fetchone()[0]
            assert matchup_count > 0, "Should have matchups"
            print(f"✓ {matchup_count} matchups loaded")

            # Test roster slots loaded
            cur.execute("SELECT COUNT(*) FROM roster_slots")
            roster_count = cur.fetchone()[0]
            assert roster_count > 0, "Should have roster slots"
            print(f"✓ {roster_count} roster slots loaded")

            # Test projections loaded
            cur.execute("SELECT COUNT(*) FROM player_projections")
            proj_count = cur.fetchone()[0]
            assert proj_count > 0, "Should have projections"
            print(f"✓ {proj_count} projections loaded")

            # Test valuations loaded
            cur.execute("SELECT COUNT(*) FROM player_valuations")
            val_count = cur.fetchone()[0]
            assert val_count > 0, "Should have valuations"
            print(f"✓ {val_count} valuations loaded")

    finally:
        conn.close()


def test_foreign_key_relationships():
    """Test that foreign key relationships are intact."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Test player stats link to players
            cur.execute("""
                SELECT COUNT(*) FROM player_stats_batting b
                LEFT JOIN players p ON b.player_id = p.id_espn
                WHERE p.id_espn IS NULL
            """)
            orphaned = cur.fetchone()[0]
            assert orphaned == 0, "All batting stats should link to valid players"
            print("✓ Batting stats all link to valid players")

            # Test roster slots link to both teams and players
            cur.execute("""
                SELECT COUNT(*) FROM roster_slots r
                LEFT JOIN teams t ON r.team_id = t.team_id
                LEFT JOIN players p ON r.player_id = p.id_espn
                WHERE t.team_id IS NULL OR p.id_espn IS NULL
            """)
            orphaned = cur.fetchone()[0]
            assert orphaned == 0, "All roster slots should link to valid teams and players"
            print("✓ Roster slots all link to valid teams and players")

            # Test matchups link to teams
            cur.execute("""
                SELECT COUNT(*) FROM matchups m
                LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                WHERE m.team1_id IS NOT NULL AND t1.team_id IS NULL
            """)
            orphaned = cur.fetchone()[0]
            assert orphaned == 0, "All matchups should link to valid teams"
            print("✓ Matchups all link to valid teams")

    finally:
        conn.close()


def test_sample_data_quality():
    """Spot check some data quality."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Test players have names
            cur.execute("SELECT COUNT(*) FROM players WHERE name IS NULL OR name = ''")
            null_names = cur.fetchone()[0]
            assert null_names == 0, "All players should have names"
            print("✓ All players have names")

            # Test teams have league_id
            cur.execute("SELECT COUNT(*) FROM teams WHERE league_id IS NULL")
            null_leagues = cur.fetchone()[0]
            assert null_leagues == 0, "All teams should have league_id"
            print("✓ All teams have league_id")

            # Test stats have player_id
            cur.execute("SELECT COUNT(*) FROM player_stats_batting WHERE player_id IS NULL")
            null_players = cur.fetchone()[0]
            assert null_players == 0, "All stats should have player_id"
            print("✓ All batting stats have player_id")

            # Test we have some numeric stats (not all NULL)
            cur.execute("SELECT COUNT(*) FROM player_stats_batting WHERE \"HR\" > 0")
            hr_count = cur.fetchone()[0]
            assert hr_count > 0, "Should have some home runs in batting stats"
            print(f"✓ Found {hr_count} players with HRs")

            # Test we have some pitching stats
            cur.execute("SELECT COUNT(*) FROM player_stats_pitching WHERE \"K\" > 0")
            k_count = cur.fetchone()[0]
            assert k_count > 0, "Should have some strikeouts in pitching stats"
            print(f"✓ Found {k_count} pitchers with strikeouts")

    finally:
        conn.close()


def test_jsonb_fields():
    """Test that JSONB fields were loaded correctly."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Test eligible_slots is valid JSON
            cur.execute("""
                SELECT COUNT(*) FROM players
                WHERE eligible_slots IS NOT NULL
                AND jsonb_array_length(eligible_slots) > 0
            """)
            json_count = cur.fetchone()[0]
            assert json_count > 0, "Should have players with eligible_slots"
            print(f"✓ {json_count} players have eligible_slots JSON")

            # Test projections is valid JSON
            cur.execute("""
                SELECT COUNT(*) FROM player_projections
                WHERE projections IS NOT NULL
            """)
            proj_count = cur.fetchone()[0]
            assert proj_count > 0, "Should have projections JSON"
            print(f"✓ {proj_count} projections with valid JSON")

    finally:
        conn.close()


if __name__ == "__main__":
    # Allow running directly: python -m pytest tests/test_load_integration.py -v
    pytest.main([__file__, "-v", "-s"])
