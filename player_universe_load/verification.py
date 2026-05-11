#!/usr/bin/env python3
"""Database verification utilities."""

import os
from .db import get_connection


def _verify_single_database(db_name: str, db_url: str):
    """Verify a single database."""
    print(f"\n{'='*60}")
    print(f"📊 Verifying {db_name}")
    print(f"{'='*60}")

    # Set the DATABASE_URL for this specific check
    os.environ["DATABASE_URL"] = db_url

    try:
        conn = get_connection()
    except Exception as e:
        print(f"\n❌ Failed to connect to {db_name}: {e}\n")
        return False

    try:
        with conn.cursor() as cur:
            # Check all tables
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]

            if not tables:
                print(f"\n⚠️  No tables found in {db_name}\n")
                return False

            print(f"\n✅ Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table}")

            print(f"\n{'='*60}")
            print("\n📈 Table Counts:\n")

            # Get counts for each table
            total_rows = 0
            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                total_rows += count
                status = "✓" if count > 0 else "⚠️"
                print(f"   {status} {table:30s} {count:6,d} rows")

            if total_rows == 0:
                print(f"\n⚠️  All tables are empty in {db_name}!")
                return False

            print(f"\n   {'Total:':30s} {total_rows:6,d} rows")

            print(f"\n{'='*60}")
            print("\n🎯 Sample Queries:\n")

            # Sample queries with headers
            queries = [
                ("Top 5 HR hitters", """
                    SELECT p.name, s."HR", s."AVG"::numeric(4,3), s."RBI"
                    FROM players p
                    JOIN player_stats_batting s ON p.id_espn = s.player_id
                    WHERE s.stat_period = 'current_season' AND s."HR" IS NOT NULL
                    ORDER BY s."HR" DESC
                    LIMIT 5
                """, ["Name", "HR", "AVG", "RBI"]),
                ("Top 5 K pitchers", """
                    SELECT p.name, s."K", s."ERA"::numeric(4,2), s."WHIP"::numeric(4,2)
                    FROM players p
                    JOIN player_stats_pitching s ON p.id_espn = s.player_id
                    WHERE s.stat_period = 'current_season' AND s."K" IS NOT NULL
                    ORDER BY s."K" DESC
                    LIMIT 5
                """, ["Name", "K", "ERA", "WHIP"]),
                ("Top 5 teams by win %", """
                    SELECT t.team_name, t.wins, t.losses, t.win_percentage::numeric(5,3)
                    FROM teams t
                    WHERE t.wins IS NOT NULL
                    ORDER BY t.win_percentage DESC NULLS LAST
                    LIMIT 5
                """, ["Team", "W", "L", "Win%"]),
            ]

            for title, query, headers in queries:
                print(f"\n{title}:")
                cur.execute(query)
                rows = cur.fetchall()
                if rows:
                    # Build formatted rows first to determine column widths
                    formatted_rows = []
                    for row in rows:
                        formatted_row = []
                        for i, val in enumerate(row):
                            if val is None:
                                formatted_row.append("--")
                            elif isinstance(val, (int, float)):
                                formatted_row.append(str(val))
                            else:
                                s = str(val)
                                if len(s) > 30:
                                    s = s[:27] + "..."
                                formatted_row.append(s)
                        formatted_rows.append(formatted_row)

                    # Calculate column widths (max of header and data)
                    col_widths = []
                    for i, header in enumerate(headers):
                        max_width = len(header)
                        for row in formatted_rows:
                            max_width = max(max_width, len(row[i]))
                        col_widths.append(max_width)

                    # Print header (left-align first column, right-align rest)
                    header_parts = [f"{headers[0]:<{col_widths[0]}}"]
                    header_parts.extend(f"{h:>{col_widths[i]}}" for i, h in enumerate(headers[1:], 1))
                    print("   " + "  ".join(header_parts))
                    print("   " + "-" * (sum(col_widths) + 2 * (len(col_widths) - 1)))

                    # Print rows (left-align first column, right-align rest)
                    for row in formatted_rows:
                        row_parts = [f"{row[0]:<{col_widths[0]}}"]
                        row_parts.extend(f"{row[i]:>{col_widths[i]}}" for i in range(1, len(row)))
                        print("   " + "  ".join(row_parts))
                else:
                    print("   (no results)")

            print(f"\n{'='*60}")
            print(f"\n✅ {db_name} verification complete!\n")
            return True

    finally:
        conn.close()


def verify_database():
    """Verify both local and remote databases."""
    print("\n🔍 Database Verification Tool\n")

    local_url = os.environ.get(
        "LOCAL_DATABASE_URL", "postgresql://localhost/fantasy_baseball"
    )
    print("🏠 Checking LOCAL database first...")
    local_ok = _verify_single_database("Local PostgreSQL", local_url)

    # NEON_DATABASE_URL is a stable config value — never overwritten by the
    # local-target switch above, so a plain os.environ lookup is enough.
    print("\n\n☁️  Checking NEON database...")
    NEON_URL = os.environ.get("NEON_DATABASE_URL")
    if NEON_URL:
        neon_ok = _verify_single_database("Neon PostgreSQL", NEON_URL)
    else:
        print("\n⚠️  Skipping Neon verification: No NEON_DATABASE_URL in environment")
        neon_ok = None

    # Summary
    print("\n" + "="*60)
    print("📋 Summary")
    print("="*60)
    print(f"   Local database:  {'✅ OK' if local_ok else '❌ Empty or unavailable'}")
    if neon_ok is not None:
        print(f"   Neon database:   {'✅ OK' if neon_ok else '❌ Empty or unavailable'}")
    else:
        print(f"   Neon database:   ⚠️  Not configured")
    print("="*60 + "\n")
