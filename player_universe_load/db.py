#!/usr/bin/env python3
"""Database connection and schema management."""

import json
import os
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv

# Load .env from project root so DATABASE_URL is available in os.environ
load_dotenv()


def get_connection():
    """Get database connection."""
    print("🔌 Connecting to database...")

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL not found. Set it in .env at the project root."
        )

    try:
        conn = psycopg2.connect(db_url)
        # Test connection
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            result = cur.fetchone()
            if result:
                version = result[0]
                print("   ✓ Connected to PostgreSQL")
                print(f"   Version: {version.split(',')[0]}")
        return conn
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        raise


def execute_schema_file(conn, schema_file: Path) -> None:
    """Execute a SQL schema file."""
    with conn.cursor() as cur:
        sql = schema_file.read_text()
        cur.execute(sql)
    conn.commit()
    print(f"✓ Executed {schema_file.name}")


def init_schema(conn) -> None:
    """Initialize database schema by executing all schema files in order."""
    schema_dir = Path(__file__).parent / "schemas"
    schema_files = sorted(schema_dir.glob("*.sql"))

    print(f"Initializing schema with {len(schema_files)} files...")
    for schema_file in schema_files:
        execute_schema_file(conn, schema_file)
    print("✓ Schema initialized")


def bulk_insert(conn, table: str, columns: list[str], rows: list[tuple]) -> int:
    """Bulk insert rows into table."""
    if not rows:
        return 0

    print(f"   💾 Inserting {len(rows):,} rows into {table}...", end="", flush=True)

    with conn.cursor() as cur:
        placeholders = ",".join(["%s"] * len(columns))
        # Quote all column names to handle mixed case and special chars
        cols = ",".join(f'"{c}"' for c in columns)

        # For player_stats tables, use ON CONFLICT DO UPDATE to handle two-way players
        if table in ("player_stats_batting", "player_stats_pitching"):
            # Update all columns except the unique constraint columns
            update_cols = [
                c for c in columns if c not in ("player_id", "season_id", "stat_period")
            ]
            updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
            sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT (player_id, season_id, stat_period) DO UPDATE SET {updates}"
        else:
            sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        # Show progress for large inserts
        if len(rows) > 100:
            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                cur.executemany(sql, batch)
                progress = min(i + batch_size, len(rows))
                print(
                    f"\r   💾 Inserting {len(rows):,} rows into {table}... {progress:,}/{len(rows):,}",
                    end="",
                    flush=True,
                )
        else:
            cur.executemany(sql, rows)

    conn.commit()
    print(f"\r   ✓ Inserted {len(rows):,} rows into {table}     ")
    return len(rows)


def json_serialize(obj: Any) -> str | None:
    """Serialize object to JSON string, return None if obj is None."""
    return json.dumps(obj) if obj is not None else None


def get_table_columns(conn, table: str) -> set[str]:
    """Get all column names for a table."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """,
            (table,),
        )
        return {row[0] for row in cur.fetchall()}


def validate_schema(
    conn, table: str, columns: list[str]
) -> tuple[bool, list[str], list[str]]:
    """
    Validate that columns match the database schema.

    Returns:
        (is_valid, missing_in_db, extra_in_data)
    """
    db_columns = get_table_columns(conn, table)
    data_columns = set(columns)

    missing_in_db = sorted(data_columns - db_columns)
    extra_in_data = sorted(db_columns - data_columns)

    # Filter out auto-generated columns that are OK to be missing from data
    extra_in_data = [
        col for col in extra_in_data if col not in ("id", "created_at", "updated_at")
    ]

    is_valid = len(missing_in_db) == 0
    return is_valid, missing_in_db, extra_in_data
