#!/usr/bin/env python3
"""
Configuration module for database connection
"""

# Import sensitive credentials
try:
    from .secrets import DATABASE_URL
except ImportError:
    try:
        from secrets import DATABASE_URL  # type: ignore
    except ImportError:
        # Fallback for development
        print("WARNING: secrets.py not found. Using fallback connection.")
        DATABASE_URL = ""

# Path to the transformed JSON file
JSON_FILE_PATH: str = (
    "/Users/Shared/BaseballHQ/resources/transform/player_universe_trxd.json"
)

# Define the fields we want to insert
PLAYER_FIELDS: list[str] = [
    "id_espn",
    "id_fangraphs",
    "id_xmlbam",
    "name",
    "first_name",
    "last_name",
    "name_nonascii",
    "name_ascii",
    "display_name",
    "short_name",
    "nickname",
    "slug_espn",
    "slug_fangraphs",
    "fangraphs_api_route",
    "primary_position",
    "eligible_slots",
    "pro_team",
    "injury_status",
    "status",
    "injured",
    "active",
    "weight",
    "display_weight",
    "height",
    "display_height",
    "bats",
    "throws",
    "date_of_birth",
    "birth_place",
    "debut_year",
    "jersey",
    "headshot",
]

# SQL for creating the players table
CREATE_TABLE_SQL: str = """
CREATE TABLE players (
    id_espn INTEGER PRIMARY KEY,
    id_fangraphs VARCHAR(255),
    id_xmlbam INTEGER,
    name VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    name_nonascii VARCHAR(255),
    name_ascii VARCHAR(255),
    display_name VARCHAR(255),
    short_name VARCHAR(255),
    nickname VARCHAR(255),
    slug_espn VARCHAR(255),
    slug_fangraphs VARCHAR(255),
    fangraphs_api_route VARCHAR(255),
    primary_position VARCHAR(255),
    eligible_slots TEXT,
    pro_team VARCHAR(255),
    injury_status VARCHAR(255),
    status VARCHAR(255),
    injured BOOLEAN,
    active BOOLEAN,
    weight NUMERIC,
    display_weight VARCHAR(255),
    height INTEGER,
    display_height VARCHAR(255),
    bats VARCHAR(255),
    throws VARCHAR(255),
    date_of_birth VARCHAR(255),
    birth_place JSONB,
    debut_year INTEGER,
    jersey INTEGER,
    headshot VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
