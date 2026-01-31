#!/usr/bin/env python3
"""Database verification utilities."""

from .db import get_connection


def verify_database():
    """Verify database structure and data."""
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            print("\n📊 Database Verification\n")
            print("=" * 60)

            # Check all tables
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]

            print(f"\n✅ Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table}")

            print("\n" + "=" * 60)
            print("\n📈 Table Counts:\n")

            # Get counts for each table
            counts = {}
            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                counts[table] = count
                print(f"   {table:30s} {count:6d} rows")

            print("\n" + "=" * 60)
            print("\n🎯 Sample Queries:\n")

            # Sample queries
            queries = [
                ("Top 5 HR hitters", """
                    SELECT p.name, s."HR", s."AVG", s."RBI"
                    FROM players p
                    JOIN player_stats_batting s ON p.id_espn = s.player_id
                    WHERE s.stat_period = 'current_season' AND s."HR" IS NOT NULL
                    ORDER BY s."HR" DESC
                    LIMIT 5
                """),
                ("Top 5 K pitchers", """
                    SELECT p.name, s."K", s."ERA", s."WHIP"
                    FROM players p
                    JOIN player_stats_pitching s ON p.id_espn = s.player_id
                    WHERE s.stat_period = 'current_season' AND s."K" IS NOT NULL
                    ORDER BY s."K" DESC
                    LIMIT 5
                """),
                ("Teams by roster size", """
                    SELECT t.team_name, COUNT(r.player_id) as roster_size
                    FROM teams t
                    LEFT JOIN roster_slots r ON t.team_id = r.team_id
                    GROUP BY t.team_id, t.team_name
                    ORDER BY roster_size DESC
                """),
            ]

            for title, query in queries:
                print(f"\n{title}:")
                cur.execute(query)
                rows = cur.fetchall()
                for row in rows:
                    print(f"   {row}")

            print("\n" + "=" * 60)
            print("\n✅ Verification complete!\n")

    finally:
        conn.close()
