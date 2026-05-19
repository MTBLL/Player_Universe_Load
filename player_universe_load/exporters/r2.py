"""Upload parquet artifacts to Cloudflare R2 (or any S3-compatible backend).

Files live in R2; metadata (object_key, sha256, size, row_count) lives in
the ``parquet_artifacts`` table in Postgres. This is the "files in R2,
metadata in Neon" pattern — viz apps query Postgres for the latest
artifact pointers, fetch the binary from R2 directly, and verify against
the recorded sha256.

S3 PUT is atomic — single-object overwrite — so a partial upload never
surfaces to readers. We compute sha256 locally and record it after a
successful PUT, so the metadata row only exists when the object does.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config

from .parquet import EXPORTED_TABLES, PARQUET_DIR

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class R2Config:
    """R2 connection config read from environment variables."""

    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    endpoint: str

    @classmethod
    def from_env(cls) -> "R2Config":
        """Load all required R2 env vars or raise with a useful message."""
        missing = [
            k
            for k in (
                "R2_ACCOUNT_ID",
                "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY",
                "R2_BUCKET",
                "R2_ENDPOINT",
            )
            if not os.environ.get(k)
        ]
        if missing:
            raise RuntimeError(
                f"R2 env vars missing: {', '.join(missing)}. "
                "Add them to .env at the project root."
            )
        return cls(
            account_id=os.environ["R2_ACCOUNT_ID"],
            access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            bucket=os.environ["R2_BUCKET"],
            endpoint=os.environ["R2_ENDPOINT"],
        )


def _s3_client(cfg: R2Config):
    """Build a boto3 S3 client pointed at the R2 endpoint.

    region_name='auto' is required for R2; signature_version='s3v4' matches
    R2's SigV4-only auth. addressing_style='virtual' avoids R2's
    path-style-deprecation noise.
    """
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Stream-hash a file to keep peak memory bounded for large parquets."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _row_count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def _upsert_artifact(
    conn,
    *,
    table_name: str,
    object_key: str,
    bucket: str,
    endpoint: str,
    sha256: str,
    etag: str | None,
    size_bytes: int,
    row_count: int,
) -> None:
    """Insert-or-replace one parquet_artifacts row keyed on table_name."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO parquet_artifacts
              (table_name, object_key, bucket, endpoint, sha256, etag,
               size_bytes, row_count, uploaded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (table_name) DO UPDATE SET
              object_key = EXCLUDED.object_key,
              bucket = EXCLUDED.bucket,
              endpoint = EXCLUDED.endpoint,
              sha256 = EXCLUDED.sha256,
              etag = EXCLUDED.etag,
              size_bytes = EXCLUDED.size_bytes,
              row_count = EXCLUDED.row_count,
              uploaded_at = CURRENT_TIMESTAMP
            """,
            (
                table_name,
                object_key,
                bucket,
                endpoint,
                sha256,
                etag,
                size_bytes,
                row_count,
            ),
        )
    conn.commit()


def upload_table(
    conn,
    table: str,
    cfg: R2Config | None = None,
    *,
    s3=None,
    source_dir: Path = PARQUET_DIR,
    key_prefix: str = "",
) -> dict[str, Any]:
    """Upload one parquet file to R2 and record metadata in Postgres.

    Returns a dict describing the uploaded artifact. Raises if the local
    parquet file is missing — caller is expected to run ``export-parquets``
    first.
    """
    cfg = cfg or R2Config.from_env()
    s3 = s3 or _s3_client(cfg)

    local_path = source_dir / f"{table}.parquet"
    if not local_path.exists():
        raise FileNotFoundError(
            f"Local parquet not found: {local_path}. Run export-parquets first."
        )

    sha256 = _sha256_file(local_path)
    size_bytes = local_path.stat().st_size
    object_key = f"{key_prefix}{table}.parquet" if key_prefix else f"{table}.parquet"

    # S3 PUT is atomic per object; concurrent readers see either the
    # previous version or the new one, never a partial.
    with local_path.open("rb") as f:
        resp = s3.put_object(
            Bucket=cfg.bucket,
            Key=object_key,
            Body=f,
            ContentType="application/vnd.apache.parquet",
            Metadata={"sha256": sha256},
        )
    etag = (resp.get("ETag") or "").strip('"') or None

    row_count = _row_count(conn, table)

    _upsert_artifact(
        conn,
        table_name=table,
        object_key=object_key,
        bucket=cfg.bucket,
        endpoint=cfg.endpoint,
        sha256=sha256,
        etag=etag,
        size_bytes=size_bytes,
        row_count=row_count,
    )

    logger.info(
        "Uploaded %s -> s3://%s/%s (%d bytes, sha256=%s)",
        table,
        cfg.bucket,
        object_key,
        size_bytes,
        sha256[:16],
    )
    return {
        "table": table,
        "object_key": object_key,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "etag": etag,
        "row_count": row_count,
    }


def upload_all(
    conn,
    cfg: R2Config | None = None,
    *,
    source_dir: Path = PARQUET_DIR,
    key_prefix: str = "",
) -> list[dict[str, Any]]:
    """Upload every table in EXPORTED_TABLES; return per-table result dicts.

    Reuses a single boto3 S3 client across uploads so the TLS connection
    and signing context aren't rebuilt 12 times.
    """
    cfg = cfg or R2Config.from_env()
    s3 = _s3_client(cfg)
    results: list[dict[str, Any]] = []
    for table in EXPORTED_TABLES:
        try:
            results.append(
                upload_table(
                    conn, table, cfg, s3=s3, source_dir=source_dir, key_prefix=key_prefix
                )
            )
        except Exception as e:
            logger.error("Failed to upload %s: %s", table, e)
            raise
    return results
