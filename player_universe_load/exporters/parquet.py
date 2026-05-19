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

# All NUMERIC values are stored as decimal128(18, 3): 15 integer digits + 3
# fractional digits, lossless within that range. Quantize with ROUND_HALF_UP
# so .5 rounds up (regulatory accounting convention), not banker's rounding.
_NUMERIC_PRECISION = 18
_NUMERIC_SCALE = 3
_QUANTUM = Decimal("0.001")

logger = logging.getLogger(__name__)

PARQUET_DIR = Path("/Users/Shared/BaseballHQ/resources/analytics")

# Matches the 12-table schema in player_universe_load/schemas/.
# Add a new entry here when a new table is added to the schema.
EXPORTED_TABLES: tuple[str, ...] = (
    "players",
    "leagues",
    "teams",
    "matchups",
    "roster_slots",
    "league_scoring_categories",
    "player_fantasy_assignments",
    "player_stats_batting",
    "player_stats_pitching",
    "player_projections",
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
    "numeric": pa.decimal128(_NUMERIC_PRECISION, _NUMERIC_SCALE),
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
    """Normalize Decimal values for parquet emission.

    - Decimal('Infinity'/'-Infinity'/'NaN') (legal in Postgres NUMERIC,
      e.g. ERA for a pitcher with 0 IP) -> None. pyarrow rejects non-finite
      Decimals and division-by-zero isn't an analytics-correct value.
    - Finite Decimal values quantized to thousandths with ROUND_HALF_UP so
      they fit decimal128(18, 3) exactly. .5 rounds up (regulatory
      convention), not Python's default banker's rounding.
    """
    for r in rows:
        for k, v in list(r.items()):
            if not isinstance(v, Decimal):
                continue
            if not v.is_finite():
                r[k] = None
            else:
                r[k] = v.quantize(_QUANTUM, rounding=ROUND_HALF_UP)
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
        # rejects heterogeneous nested shapes). NUMERIC values quantized to
        # thousandths so they fit decimal128(18, 3) exactly. Other column
        # types come back from psycopg2 as native Python types that match
        # the declared schema directly.
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
    for table in EXPORTED_TABLES:
        try:
            paths.append(export_table(conn, table, target_dir=target_dir))
        except Exception as e:
            logger.error("Failed to export %s: %s", table, e)
            raise
    return paths
