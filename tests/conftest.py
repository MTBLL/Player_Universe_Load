"""Pytest config: give every test its own freshly-loaded copy of the database.

Each test runs against a throwaway database cloned from a template that is built
once per session (schema + test fixtures). Because ``get_connection()`` re-reads
``DATABASE_URL`` on every call and never pools, pointing that env var at the
per-test clone transparently isolates every connection a test opens — directly,
via a ``conn`` fixture, or inside ``load_all()``. Committed writes in one test
can no longer leak into the next, so test outcomes no longer depend on order.

The template loads from ``tests/fixtures`` (never the local ``/resources`` ETL
output), so the dataset is deterministic and identical to CI.
"""

import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest
from dotenv import load_dotenv

load_dotenv()

# Source of the host/credentials/port that every test database reuses. Tests
# never run against this DB directly — we only borrow its connection target and
# swap the database name.
_BASE_URL = os.environ.get(
    "LOCAL_DATABASE_URL", "postgresql://localhost/fantasy_baseball"
)
_TEMPLATE_DB = "pul_test_template"


def _url_with_db(url: str, dbname: str) -> str:
    """Return ``url`` with its path (database name) replaced by ``dbname``."""
    return urlunsplit(urlsplit(url)._replace(path=f"/{dbname}"))


# CREATE/DROP DATABASE cannot run while connected to the target database, nor
# inside a transaction block — so admin DDL runs against the default `postgres`
# maintenance database on an autocommit connection.
_ADMIN_URL = _url_with_db(_BASE_URL, "postgres")


def _admin_conn():
    conn = psycopg2.connect(_ADMIN_URL)
    conn.autocommit = True
    return conn


def _drop_db(cur, dbname: str) -> None:
    """Force-disconnect lingering backends, then drop the database."""
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (dbname,),
    )
    cur.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


@pytest.fixture(scope="session", autouse=True)
def _loaded_template():
    """Build a schema+fixtures template database once for the whole session."""
    import player_universe_load.__main__ as main_mod

    admin = _admin_conn()
    try:
        with admin.cursor() as cur:
            _drop_db(cur, _TEMPLATE_DB)
            cur.execute(f'CREATE DATABASE "{_TEMPLATE_DB}"')
    finally:
        admin.close()

    template_url = _url_with_db(_BASE_URL, _TEMPLATE_DB)
    prev_env = os.environ.get("DATABASE_URL")
    prev_transform = main_mod.TRANSFORM_DIR
    prev_load = main_mod.LOAD_DIR
    os.environ["DATABASE_URL"] = template_url
    # Point the ETL dirs at nonexistent paths so load_all() falls back to
    # FIXTURES_DIR (tests/fixtures) — deterministic and matching CI.
    main_mod.TRANSFORM_DIR = Path("/nonexistent/transform")
    main_mod.LOAD_DIR = Path("/nonexistent/load")
    try:
        main_mod.load_all()
    finally:
        main_mod.TRANSFORM_DIR = prev_transform
        main_mod.LOAD_DIR = prev_load
        if prev_env is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev_env

    yield template_url

    admin = _admin_conn()
    try:
        with admin.cursor() as cur:
            _drop_db(cur, _TEMPLATE_DB)
    finally:
        admin.close()


@pytest.fixture(autouse=True)
def isolated_db(_loaded_template):
    """Clone the template into a throwaway database for this single test.

    Sets ``DATABASE_URL`` to the clone for the duration of the test, then drops
    it. Autouse + function scope means every test is isolated with no per-test
    boilerplate; ``get_connection()`` picks up the clone automatically.
    """
    dbname = f"pul_test_{uuid.uuid4().hex}"
    admin = _admin_conn()
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{dbname}" TEMPLATE "{_TEMPLATE_DB}"')
    finally:
        admin.close()

    prev_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _url_with_db(_BASE_URL, dbname)
    try:
        yield
    finally:
        if prev_env is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev_env
        admin = _admin_conn()
        try:
            with admin.cursor() as cur:
                _drop_db(cur, dbname)
        finally:
            admin.close()
