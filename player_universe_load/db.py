#!/usr/bin/env python3
"""Database connection and schema management."""

import json
import os
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

# Single global console keeps Rich output consistent across modules and
# behaves correctly under pytest capsys (writes through sys.stdout).
console = Console()

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
    """Bulk insert rows into table with a Rich progress bar for large inserts."""
    if not rows:
        return 0

    with conn.cursor() as cur:
        placeholders = ",".join(["%s"] * len(columns))
        # Quote all column names to handle mixed case and special chars
        cols = ",".join(f'"{c}"' for c in columns)

        # For player_stats tables, use ON CONFLICT DO UPDATE to handle two-way players
        if table in ("player_stats_batting", "player_stats_pitching"):
            update_cols = [
                c for c in columns if c not in ("player_id", "season_id", "stat_period")
            ]
            updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
            sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT (player_id, season_id, stat_period) DO UPDATE SET {updates}"
        else:
            sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        # Live progress bar only for batched inserts. Small inserts skip
        # the bar AND skip the "✓ Inserted" summary line — they happen too
        # fast to be worth either log artifact.
        if len(rows) > 100:
            batch_size = 100
            # transient=False — Postgres inserts are network/SQL API work,
            # persist the bar so elapsed time stays in the log. The persisted
            # bar IS the log entry; no separate "✓ Inserted" follow-up.
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold]💾 {task.description}"),
                BarColumn(bar_width=30),
                MofNCompleteColumn(),
                TextColumn("rows"),
                TimeElapsedColumn(),
                console=console,
                transient=False,
            ) as progress:
                task = progress.add_task(table, total=len(rows))
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    cur.executemany(sql, batch)
                    progress.update(task, advance=len(batch))
            conn.commit()
        else:
            cur.executemany(sql, rows)
            conn.commit()
            console.print(
                f"   [green]✓[/green] Inserted [bold]{len(rows):,}[/bold] rows into "
                f"[cyan]{table}[/cyan]"
            )

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
