#!/usr/bin/env python3
"""Neon database smoke test.

Read-only sanity check against the Neon database:
- Connects via NEON_DATABASE_URL.
- Confirms every expected table exists.
- Confirms each table has rows (no silently empty target tables).
- Confirms player_valuations has all 5 valuation_type scenarios.
- Exits non-zero on any assertion failure.

Does NOT modify any data. Safe to run at any frequency.
"""

from __future__ import annotations

import os
import sys

import psycopg2

EXPECTED_TABLES = (
    "players",
    "leagues",
    "league_scoring_categories",
    "teams",
    "matchups",
    "roster_slots",
    "player_stats_batting",
    "player_stats_pitching",
    "player_projections",
    "player_valuations",
    "player_valuation_details",
    "player_fantasy_assignments",
)

EXPECTED_VALUATION_TYPES = {"preseason", "updated", "ros", "synthetic", "current"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    url = os.environ.get("NEON_DATABASE_URL")
    if not url:
        fail("NEON_DATABASE_URL env var not set")

    print("Connecting to Neon...")
    conn = psycopg2.connect(url)
    conn.set_session(readonly=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            print(f"  connected: {version[:50]}...")

            print("\nChecking tables...")
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            present = {r[0] for r in cur.fetchall()}
            missing = set(EXPECTED_TABLES) - present
            if missing:
                fail(f"missing tables: {sorted(missing)}")
            print(f"  all {len(EXPECTED_TABLES)} expected tables present")

            print("\nChecking row counts...")
            for table in EXPECTED_TABLES:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cur.fetchone()[0]
                if count == 0:
                    fail(f"{table} is empty")
                print(f"  {table:<32} {count:>10,} rows")

            print("\nChecking valuation scenarios...")
            cur.execute(
                "SELECT DISTINCT valuation_type FROM player_valuations"
            )
            found_types = {r[0] for r in cur.fetchall()}
            missing_types = EXPECTED_VALUATION_TYPES - found_types
            if missing_types:
                fail(f"missing valuation_type scenarios: {sorted(missing_types)}")
            print(f"  all 5 scenarios present: {sorted(found_types)}")

            print("\nChecking referential integrity (sample join)...")
            cur.execute(
                "SELECT COUNT(*) FROM player_valuations v "
                "LEFT JOIN players p ON v.player_id = p.id_espn "
                "WHERE p.id_espn IS NULL"
            )
            orphans = cur.fetchone()[0]
            if orphans > 0:
                fail(f"{orphans} valuation rows reference missing players")
            print("  player_valuations -> players: no orphans")
    finally:
        conn.close()

    print("\nSMOKE OK")


if __name__ == "__main__":
    main()
