#!/usr/bin/env python3
"""Tests for the R2 uploader.

Network is fully mocked — tests do not hit Cloudflare. Real-network
verification lives outside the pytest suite (`upload-parquets` CLI command
run manually against the configured bucket).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from player_universe_load import db
from player_universe_load.exporters import r2


# -------------------- R2Config --------------------


def test_r2config_from_env_happy(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sk")
    monkeypatch.setenv("R2_BUCKET", "bk")
    monkeypatch.setenv("R2_ENDPOINT", "https://acct.r2.cloudflarestorage.com")
    cfg = r2.R2Config.from_env()
    assert cfg.account_id == "acct"
    assert cfg.bucket == "bk"
    assert cfg.endpoint.endswith(".r2.cloudflarestorage.com")


def test_r2config_from_env_missing(monkeypatch):
    for k in (
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET",
        "R2_ENDPOINT",
    ):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="R2 env vars missing"):
        r2.R2Config.from_env()


# -------------------- Helpers --------------------


def test_sha256_file_matches_hashlib(tmp_path: Path):
    p = tmp_path / "f.bin"
    payload = b"hello\x00world" * 1000
    p.write_bytes(payload)
    assert r2._sha256_file(p) == hashlib.sha256(payload).hexdigest()


def test_s3_client_uses_r2_endpoint_and_signing(monkeypatch):
    """Confirm boto3 client is created with R2-correct args."""
    cfg = r2.R2Config(
        account_id="acct",
        access_key_id="ak",
        secret_access_key="sk",
        bucket="bk",
        endpoint="https://acct.r2.cloudflarestorage.com",
    )
    with patch("player_universe_load.exporters.r2.boto3.client") as mk:
        r2._s3_client(cfg)
        mk.assert_called_once()
        kwargs = mk.call_args.kwargs
        assert kwargs["endpoint_url"] == cfg.endpoint
        assert kwargs["aws_access_key_id"] == "ak"
        assert kwargs["aws_secret_access_key"] == "sk"
        assert kwargs["region_name"] == "auto"


# -------------------- upload_table --------------------


@pytest.fixture
def cfg() -> r2.R2Config:
    return r2.R2Config(
        account_id="acct",
        access_key_id="ak",
        secret_access_key="sk",
        bucket="testbucket",
        endpoint="https://acct.r2.cloudflarestorage.com",
    )


def test_upload_table_missing_file_raises(cfg, tmp_path: Path):
    conn = db.get_connection()
    try:
        s3 = MagicMock()
        with pytest.raises(FileNotFoundError, match="Run export-parquets first"):
            r2.upload_table(conn, "players", cfg, s3=s3, source_dir=tmp_path)
        s3.put_object.assert_not_called()
    finally:
        conn.close()


def test_upload_table_writes_metadata_row(cfg, tmp_path: Path):
    """Happy path: file exists, put_object succeeds, metadata row inserted."""
    pq_file = tmp_path / "players.parquet"
    pq_file.write_bytes(b"fake parquet bytes")

    s3 = MagicMock()
    s3.put_object.return_value = {"ETag": '"abc123etag"'}

    conn = db.get_connection()
    try:
        # Clear any prior artifact for this table to test the INSERT branch
        with conn.cursor() as cur:
            cur.execute("DELETE FROM parquet_artifacts WHERE table_name = 'players'")
            conn.commit()

        result = r2.upload_table(conn, "players", cfg, s3=s3, source_dir=tmp_path)

        # Boto called with R2-correct payload
        s3.put_object.assert_called_once()
        call_kwargs = s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "testbucket"
        assert call_kwargs["Key"] == "players.parquet"
        assert call_kwargs["ContentType"] == "application/vnd.apache.parquet"
        assert "sha256" in call_kwargs["Metadata"]

        # Metadata row recorded
        with conn.cursor() as cur:
            cur.execute(
                "SELECT object_key, sha256, etag, size_bytes, row_count, bucket "
                "FROM parquet_artifacts WHERE table_name = 'players'"
            )
            row = cur.fetchone()
            assert row is not None
            object_key, sha256, etag, size_bytes, row_count, bucket = row
            assert object_key == "players.parquet"
            assert sha256 == hashlib.sha256(b"fake parquet bytes").hexdigest()
            assert etag == "abc123etag"  # quotes stripped
            assert size_bytes == len(b"fake parquet bytes")
            assert row_count == result["row_count"]
            assert bucket == "testbucket"
    finally:
        conn.close()


def test_upload_table_upsert_replaces_existing(cfg, tmp_path: Path):
    """Re-upload same table -> UPSERT updates rather than duplicating row."""
    pq_file = tmp_path / "teams.parquet"
    pq_file.write_bytes(b"v1")

    s3 = MagicMock()
    s3.put_object.return_value = {"ETag": '"v1tag"'}

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM parquet_artifacts WHERE table_name = 'teams'")
            conn.commit()

        r2.upload_table(conn, "teams", cfg, s3=s3, source_dir=tmp_path)
        # Second upload with different bytes
        pq_file.write_bytes(b"v2-longer")
        s3.put_object.return_value = {"ETag": '"v2tag"'}
        r2.upload_table(conn, "teams", cfg, s3=s3, source_dir=tmp_path)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), MAX(size_bytes), MAX(etag) "
                "FROM parquet_artifacts WHERE table_name = 'teams'"
            )
            count, size, etag = cur.fetchone()
            assert count == 1  # UPSERT, not insert
            assert size == len(b"v2-longer")
            assert etag == "v2tag"
    finally:
        conn.close()


def test_upload_table_etag_none_when_missing(cfg, tmp_path: Path):
    """If S3 doesn't return ETag, the metadata row stores NULL."""
    pq_file = tmp_path / "leagues.parquet"
    pq_file.write_bytes(b"no-etag")

    s3 = MagicMock()
    s3.put_object.return_value = {}  # no ETag

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM parquet_artifacts WHERE table_name = 'leagues'")
            conn.commit()
        r2.upload_table(conn, "leagues", cfg, s3=s3, source_dir=tmp_path)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT etag FROM parquet_artifacts WHERE table_name = 'leagues'"
            )
            assert cur.fetchone()[0] is None
    finally:
        conn.close()


def test_upload_table_key_prefix(cfg, tmp_path: Path):
    """key_prefix is prepended to the object key (for env-scoped uploads)."""
    pq_file = tmp_path / "players.parquet"
    pq_file.write_bytes(b"x")
    s3 = MagicMock()
    s3.put_object.return_value = {"ETag": '"e"'}

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM parquet_artifacts WHERE table_name = 'players'")
            conn.commit()
        r2.upload_table(
            conn, "players", cfg, s3=s3, source_dir=tmp_path, key_prefix="prod/2026/"
        )
        assert s3.put_object.call_args.kwargs["Key"] == "prod/2026/players.parquet"
    finally:
        conn.close()


# -------------------- upload_all --------------------


def test_upload_all_iterates_exported_tables(cfg, tmp_path: Path):
    """Writes every EXPORTED_TABLES entry, returns one result dict each."""
    from player_universe_load.exporters.parquet import EXPORTED_TABLES

    for t in EXPORTED_TABLES:
        (tmp_path / f"{t}.parquet").write_bytes(b"x")

    s3 = MagicMock()
    s3.put_object.return_value = {"ETag": '"e"'}

    conn = db.get_connection()
    try:
        with patch.object(r2, "_s3_client", return_value=s3):
            results = r2.upload_all(conn, cfg, source_dir=tmp_path)
        assert len(results) == len(EXPORTED_TABLES)
        assert {r["table"] for r in results} == set(EXPORTED_TABLES)
        # One PUT per table
        assert s3.put_object.call_count == len(EXPORTED_TABLES)
    finally:
        conn.close()


def test_upload_all_propagates_failure(cfg, tmp_path: Path):
    """First upload fails -> exception bubbles out, loop short-circuits."""
    from player_universe_load.exporters.parquet import EXPORTED_TABLES

    # Only create the file for the first table -> rest fail with FileNotFoundError
    (tmp_path / f"{EXPORTED_TABLES[0]}.parquet").write_bytes(b"x")

    s3 = MagicMock()
    s3.put_object.return_value = {"ETag": '"e"'}

    conn = db.get_connection()
    try:
        with patch.object(r2, "_s3_client", return_value=s3):
            with pytest.raises(FileNotFoundError):
                r2.upload_all(conn, cfg, source_dir=tmp_path)
    finally:
        conn.close()


# -------------------- CLI integration --------------------


def test_cli_upload_parquets_command(monkeypatch):
    """cli.upload_parquets calls upload_all with a real connection."""
    from player_universe_load import cli

    with patch(
        "player_universe_load.cli.upload_all",
        return_value=[
            {"table": "t1", "size_bytes": 100, "object_key": "t1.parquet",
             "sha256": "x" * 64, "etag": "e", "row_count": 1},
        ],
    ) as ua:
        cli.upload_parquets()
        ua.assert_called_once()


def test_cli_main_upload_parquets_subcommand(monkeypatch):
    import sys
    from player_universe_load import cli

    monkeypatch.setattr(sys, "argv", ["player-universe-load", "upload-parquets"])
    with patch("player_universe_load.cli.upload_parquets") as up:
        assert cli.main() == 0
        up.assert_called_once()
