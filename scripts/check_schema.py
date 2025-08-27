#!/usr/bin/env python3
"""
Check the schema of the players table
"""

import psycopg2

try:
    from .config import DATABASE_URL
except ImportError:
    from config import DATABASE_URL  # type: ignore


def main() -> None:
    """Check the schema of the players table"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
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
