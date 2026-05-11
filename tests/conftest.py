"""Pytest configuration: point tests at the local database before they import db."""

import os

from dotenv import load_dotenv

load_dotenv()

# Tests hit get_connection() directly (no CLI layer), so we have to do here
# what load_local() does at runtime: resolve LOCAL_DATABASE_URL (with a
# localhost fallback) and expose it as DATABASE_URL for the test session.
os.environ["DATABASE_URL"] = os.environ.get(
    "LOCAL_DATABASE_URL", "postgresql://localhost/fantasy_baseball"
)
