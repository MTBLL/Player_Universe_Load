#!/usr/bin/env python3
"""
Verify the players table structure and query capability
"""
from typing import Any, Dict, List, Optional, Tuple, Union
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection, cursor

try:
    from .config import DATABASE_URL
except ImportError:
    from config import DATABASE_URL  # type: ignore

def main() -> None:
    """Verify the players table structure and query capability"""
    try:
        conn: connection = psycopg2.connect(DATABASE_URL)
        cursor_obj: cursor = conn.cursor()
        
        # Get column information
        cursor_obj.execute("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'players'
            ORDER BY ordinal_position;
        """)
        
        columns: List[Tuple[str, str, Optional[str], str]] = cursor_obj.fetchall()
        print("=== Columns in players table ===")
        print("Column Name            | Data Type           | Default        | Nullable")
        print("-" * 80)
        for col in columns:
            name, data_type, default, nullable = col
            print(f"{name:22} | {data_type:20} | {str(default or '')[:15]:15} | {nullable}")
        
        # Get primary key information
        cursor_obj.execute("""
            SELECT
                tc.constraint_name, 
                tc.constraint_type,
                kcu.column_name
            FROM 
                information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'players' AND tc.constraint_type = 'PRIMARY KEY';
        """)
        
        pk_info: Optional[Tuple[str, str, str]] = cursor_obj.fetchone()
        print("\n=== Primary Key Information ===")
        if pk_info:
            print(f"Constraint Name: {pk_info[0]}")
            print(f"Constraint Type: {pk_info[1]}")
            print(f"Column Name: {pk_info[2]}")
        else:
            print("No primary key defined")
        
        # Sample query for a known player
        print("\n=== Sample Query ===")
        cursor_obj.execute("""
            SELECT id_espn, name, pro_team, primary_position, status
            FROM players
            WHERE id_espn = 32367;  -- Eugenio Suarez
        """)
        
        player: Optional[Tuple[int, str, str, str, str]] = cursor_obj.fetchone()
        if player:
            print(f"Found: ID: {player[0]}, Name: {player[1]}, Team: {player[2]}, Position: {player[3]}, Status: {player[4]}")
        else:
            print("Player not found")
        
        # Get count by team
        print("\n=== Player Count by Team ===")
        cursor_obj.execute("""
            SELECT pro_team, COUNT(*) as count
            FROM players
            GROUP BY pro_team
            ORDER BY count DESC
            LIMIT 10;
        """)
        
        teams: List[Tuple[str, int]] = cursor_obj.fetchall()
        for team in teams:
            print(f"{team[0]}: {team[1]} players")
        
        cursor_obj.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()