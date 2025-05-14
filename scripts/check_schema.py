#!/usr/bin/env python3
"""
Check the schema of the players table
"""

from typing import Dict

import psycopg2

try:
    from .config import DB_PARAMS
except ImportError:
    from config import DB_PARAMS  # type: ignore


def main() -> None:
    """Check the schema of the players table"""
    try:
        conn = psycopg2.connect(
            host=DB_PARAMS['host'],
            port=DB_PARAMS['port'],
            dbname=DB_PARAMS['dbname'],
            user=DB_PARAMS['user'],
            password=DB_PARAMS['password']
        )
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'players'
            )
        """)

        result = cursor.fetchone()
        exists = result[0] if result else False
        if not exists:
            print("Table 'players' does not exist")
            return

        # Get column information
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'players'
            ORDER BY ordinal_position;
        """)

        columns = cursor.fetchall()
        print("Columns in players table:")
        for col in columns:
            print(f"{col[0]} ({col[1]})")

        # Drop the table
        drop = input("Do you want to drop the players table? (y/n): ")
        if drop.lower() == "y":
            cursor.execute("DROP TABLE players")
            conn.commit()
            print("Table 'players' dropped successfully")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
