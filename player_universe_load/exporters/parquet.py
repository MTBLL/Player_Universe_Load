"""Export Postgres tables to parquet files for downstream analytics consumption.

Postgres is the source (not the JSON fixtures) because ON CONFLICT merges in
bulk_insert leave Postgres with the canonical state; JSON may contain conflicts
or duplicates.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from psycopg2.extras import RealDictCursor
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ..db import console

# All NUMERIC values are emitted as float64. decimal128 is unreadable by most
# browser/WASM parquet readers (apache-arrow JS, parquet-wasm, hyparquet decode
# it to null/garbage), and this dataset's only consumer reads parquet in the
# browser straight from R2. float64 is universally supported; for stats/dollars
# rounded to thousandths the value is well within float64's exact-integer range,
# so display and aggregation are lossless in practice.
# Decimals are quantized to 3 places with ROUND_HALF_UP (so .5 rounds up, the
# accounting convention) before the float cast, keeping clean 3-decimal values
# instead of float noise like 4.6080000000001.
_NUMERIC_SCALE = 3
_QUANTUM = Decimal("0.001")

logger = logging.getLogger(__name__)

PARQUET_DIR = Path("/Users/Shared/BaseballHQ/resources/analytics")

# Mirrors the schema in player_universe_load/schemas/ (minus parquet_artifacts).
# Add a new entry here when a new table is added to the schema.
EXPORTED_TABLES: tuple[str, ...] = (
    "players",
    "leagues",
    "teams",
    "matchups",
    "matchup_categories",
    "roster_slots",
    "league_scoring_categories",
    "player_fantasy_assignments",
    "player_stats_batting",
    "player_stats_pitching",
    "player_projections",
    "player_savant",
    "player_pitch_arsenal",
    "player_valuations",
    "player_valuation_details",
    "position_summary",
)
# Note: parquet_artifacts is intentionally excluded — it's the Postgres-side
# join point pointing AT the R2 objects, not itself an exported artifact.


def _table_columns(conn, table: str) -> list[tuple[str, str]]:
    """Return [(column_name, data_type), ...] from information_schema."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position",
            (table,),
        )
        cols = cur.fetchall()
    if not cols:
        raise RuntimeError(f"Table {table!r} not found in information_schema")
    return [(c[0], c[1]) for c in cols]


# Postgres `information_schema.data_type` -> pyarrow dtype.
# Conservative mapping: pick the widest sensible type so a future row of any
# legal value fits. JSONB is stored as string because the writer JSON-encodes
# JSONB columns regardless of row count.
_PG_TO_ARROW = {
    "smallint": pa.int16(),
    "integer": pa.int32(),
    "bigint": pa.int64(),
    "serial": pa.int32(),
    "bigserial": pa.int64(),
    "real": pa.float32(),
    "double precision": pa.float64(),
    "numeric": pa.float64(),
    "boolean": pa.bool_(),
    "text": pa.string(),
    "character varying": pa.string(),
    "character": pa.string(),
    "uuid": pa.string(),
    "json": pa.string(),
    "jsonb": pa.string(),
    "date": pa.date32(),
    "timestamp without time zone": pa.timestamp("us"),
    "timestamp with time zone": pa.timestamp("us", tz="UTC"),
    "time without time zone": pa.time64("us"),
    "bytea": pa.binary(),
    "ARRAY": pa.string(),
}


def _arrow_schema_for(conn, table: str) -> pa.Schema:
    """Build a pyarrow Schema with real types sourced from information_schema."""
    cols = _table_columns(conn, table)
    fields = []
    for name, pg_type in cols:
        arrow_type = _PG_TO_ARROW.get(pg_type, pa.string())
        fields.append(pa.field(name, arrow_type))
    return pa.schema(fields)


def _sanitize_decimals(rows: list[dict]) -> list[dict]:
    """Normalize Decimal values to float for parquet emission.

    The NUMERIC columns are written as float64 (browser parquet readers can't
    decode decimal128 — see _PG_TO_ARROW), so each psycopg2 Decimal is converted
    to a Python float:

    - Decimal('Infinity'/'-Infinity'/'NaN') (legal in Postgres NUMERIC,
      e.g. ERA for a pitcher with 0 IP) -> None. division-by-zero isn't an
      analytics-correct value, and a float NaN would muddy downstream queries.
    - Finite Decimal values quantized to thousandths with ROUND_HALF_UP (.5
      rounds up, accounting convention) before float() so the result is a clean
      3-decimal float rather than binary-fp noise.
    """
    for r in rows:
        for k, v in list(r.items()):
            if not isinstance(v, Decimal):
                continue
            if not v.is_finite():
                r[k] = None
            else:
                r[k] = float(v.quantize(_QUANTUM, rounding=ROUND_HALF_UP))
    return rows


def _stringify_jsonb(rows: list[dict], jsonb_cols: list[str]) -> list[dict]:
    """JSON-encode JSONB columns so pyarrow doesn't choke on heterogeneous shapes.

    pyarrow's type inference from dict/list values requires consistent shape
    across rows. JSONB columns in this schema (e.g. eligible_slots, projections,
    birth_place) deliberately vary per row, so we encode them as JSON strings.
    Readers can ``json.loads()`` to recover the structure.
    """
    if not jsonb_cols:
        return rows
    for r in rows:
        for col in jsonb_cols:
            v = r.get(col)
            if v is not None and not isinstance(v, str):
                r[col] = json.dumps(v, default=str)
    return rows


def export_table(conn, table: str, target_dir: Path = PARQUET_DIR) -> Path:
    """Read one Postgres table and write it as a parquet file with atomic swap.

    Returns the final path of the written .parquet file.

    Atomic swap: write to ``<table>.parquet.tmp`` then ``rename`` to
    ``<table>.parquet``. POSIX rename on the same filesystem is atomic, so a
    concurrent reader either sees the previous run's file or the new one,
    never a partial.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    final = target_dir / f"{table}.parquet"
    tmp = target_dir / f"{table}.parquet.tmp"
    # If a prior run died mid-write, sweep the stale tmp before retry.
    tmp.unlink(missing_ok=True)

    cols = _table_columns(conn, table)
    jsonb_cols = [name for name, dtype in cols if dtype == "jsonb"]
    schema = _arrow_schema_for(conn, table)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM {table}")
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        logger.warning("Table %s is empty; writing zero-row parquet", table)
    else:
        # JSONB columns are JSON-encoded as strings (pyarrow type-inference
        # rejects heterogeneous nested shapes). NUMERIC values are quantized to
        # thousandths and cast to float64 (browser readers can't decode
        # decimal128). Other column types come back from psycopg2 as native
        # Python types that match the declared schema directly.
        rows = _sanitize_decimals(rows)
        rows = _stringify_jsonb(rows, jsonb_cols)

    arrow_table = pa.Table.from_pylist(rows, schema=schema)

    pq.write_table(arrow_table, tmp, compression="zstd")
    tmp.rename(final)
    logger.info("Wrote %d rows to %s", len(rows), final)
    return final


def export_all(conn, target_dir: Path = PARQUET_DIR) -> list[Path]:
    """Export every table in EXPORTED_TABLES; return list of written paths."""
    paths: list[Path] = []
    # transient=False: parquet export is disk I/O (file writes), persist
    # the bar + elapsed time in the log.
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]📦 Exporting to parquet"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[current]}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("export", total=len(EXPORTED_TABLES), current="")
        for table in EXPORTED_TABLES:
            progress.update(task, current=table)
            try:
                paths.append(export_table(conn, table, target_dir=target_dir))
            except Exception as e:
                logger.error("Failed to export %s: %s", table, e)
                raise
            progress.update(task, advance=1)
    return paths
