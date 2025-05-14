#!/usr/bin/env python3
"""
Create the mtbl database on PostgreSQL
"""
from typing import Dict, Optional, Tuple
import psycopg2
from psycopg2.extensions import connection, cursor

# Database connection parameters - use postgres as the default database
POSTGRES_DB_PARAMS: Dict[str, str] = {
    "host": "mtbl.chigsmi0ar1o.us-west-1.rds.amazonaws.com",
    "port": "5432",
    "dbname": "postgres",  # Connect to default postgres database
    "user": "mtbl",
    "password": "cPHVBe5pBpLlgG27l6Sg"
}

def main() -> None:
    """Create the mtbl database if it doesn't exist"""
    try:
        # Connect to the default postgres database
        conn: connection = psycopg2.connect(
            host=POSTGRES_DB_PARAMS["host"],
            port=POSTGRES_DB_PARAMS["port"],
            dbname=POSTGRES_DB_PARAMS["dbname"],
            user=POSTGRES_DB_PARAMS["user"],
            password=POSTGRES_DB_PARAMS["password"]
        )
        conn.autocommit = True  # Important for CREATE DATABASE
        cursor_obj: cursor = conn.cursor()
        
        # Check if database exists
        cursor_obj.execute("SELECT datname FROM pg_database WHERE datname = 'mtbl';")
        exists: Optional[Tuple[str]] = cursor_obj.fetchone()
        
        if exists:
            print("Database 'mtbl' already exists")
        else:
            # Create database
            print("Creating database 'mtbl'...")
            cursor_obj.execute("CREATE DATABASE mtbl;")
            print("Database 'mtbl' created successfully")
        
        cursor_obj.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()