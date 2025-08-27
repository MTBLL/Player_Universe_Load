#!/usr/bin/env python3
"""
Create the neondb database on PostgreSQL (note: Neon automatically creates the database)
"""
from typing import Optional, Tuple
import psycopg2
from psycopg2.extensions import connection, cursor

try:
    from .config import DATABASE_URL
except ImportError:
    from config import DATABASE_URL  # type: ignore

# For Neon, we connect to the default database which is already created
# This script mainly serves as a connection test

def main() -> None:
    """Test connection to Neon database (database already exists in Neon)"""
    try:
        # Connect to the Neon database
        conn: connection = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor_obj: cursor = conn.cursor()
        
        # Test connection by getting database name
        cursor_obj.execute("SELECT current_database();")
        db_name: Optional[Tuple[str]] = cursor_obj.fetchone()
        
        if db_name:
            print(f"Successfully connected to Neon database: {db_name[0]}")
        else:
            print("Connected to Neon but couldn't determine database name")
        
        cursor_obj.close()
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to Neon database: {e}")

if __name__ == "__main__":
    main()