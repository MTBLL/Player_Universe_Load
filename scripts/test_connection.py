#!/usr/bin/env python3
"""
Script to test PostgreSQL database connection
"""
from typing import Dict, Tuple, Any, Optional
from psycopg2.extensions import connection, cursor
from player_universe_load.postgres_loader import PostgresLoader

try:
    from .config import DB_PARAMS
except ImportError:
    from config import DB_PARAMS  # type: ignore

def main() -> None:
    """Test connection to PostgreSQL database"""
    try:
        print("Initializing PostgresLoader...")
        loader = PostgresLoader(DB_PARAMS)
        
        print("Attempting to connect to database...")
        conn = loader.get_connection()
        
        print("Successfully connected to database!")
        
        # Try a simple query to further verify connection
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"PostgreSQL database version: {version[0]}")
        
        # Check if our target table already exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'players'
            )
        """)
        table_exists = cursor.fetchone()[0]
        if table_exists:
            print("The 'players' table already exists in the database.")
        else:
            print("The 'players' table does not yet exist in the database.")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Connection failed with error: {e}")

if __name__ == "__main__":
    main()