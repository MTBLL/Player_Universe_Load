#!/usr/bin/env python3
"""
Clean script to recreate the database table and upload data
"""
import json
from typing import Any, Dict, List, Optional, Tuple, Union
import psycopg2
from psycopg2.extensions import connection, cursor

try:
    from .config import DATABASE_URL, JSON_FILE_PATH, PLAYER_FIELDS, CREATE_TABLE_SQL
except ImportError:
    from config import DATABASE_URL, JSON_FILE_PATH, PLAYER_FIELDS, CREATE_TABLE_SQL  # type: ignore

def main() -> None:
    """Main function to clean and reload the players table"""
    
    print("=== Player Universe Database Load ===")
    
    # Read and validate the JSON data
    print("\n1. Reading JSON data...")
    try:
        with open(JSON_FILE_PATH, 'r') as f:
            data: List[Dict[str, Any]] = json.load(f)
        
        if not isinstance(data, list):
            print(f"Error: JSON file does not contain a list of players")
            return
        
        print(f"Found {len(data)} player records")
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return
    
    # Connect to the database
    print("\n2. Connecting to database...")
    try:
        conn: connection = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor_obj: cursor = conn.cursor()
        
        print("Successfully connected to the database")
    except Exception as e:
        print(f"Database connection error: {e}")
        return
    
    # Drop the table if it exists
    print("\n3. Dropping existing players table if it exists...")
    try:
        cursor_obj.execute("DROP TABLE IF EXISTS players")
        print("Table dropped or did not exist")
    except Exception as e:
        print(f"Error dropping table: {e}")
        return
    
    # Create the new table with id_espn as the primary key
    print("\n4. Creating new players table...")
    try:
        cursor_obj.execute(CREATE_TABLE_SQL)
        print("Table created successfully")
    except Exception as e:
        print(f"Error creating table: {e}")
        return
    
    # Insert the data
    print("\n5. Loading player data...")
    
    # Use the fields from config
    field_names: List[str] = PLAYER_FIELDS
    
    placeholders: str = ", ".join(["%s"] * len(field_names))
    insert_sql: str = f"""
    INSERT INTO players ({", ".join(field_names)})
    VALUES ({placeholders})
    """
    
    try:
        # Batch insert
        values_list: List[Tuple[Any, ...]] = []
        for record in data:
            # Skip retired players
            if record.get("status") == "retired":
                continue
                
            values: List[Any] = []
            for field_name in field_names:
                value: Any = record.get(field_name)
                
                # Handle special cases
                if field_name == "birth_place" and isinstance(value, dict):
                    value = json.dumps(value)
                elif field_name == "eligible_slots" and isinstance(value, list):
                    value = json.dumps(value)
                elif value == "":
                    value = None
                    
                values.append(value)
            
            values_list.append(tuple(values))
        
        cursor_obj.executemany(insert_sql, values_list)
        conn.commit()
        
        print(f"Successfully loaded {len(values_list)} player records into the database")
        
        # Verify the count
        cursor_obj.execute("SELECT COUNT(*) FROM players")
        result = cursor_obj.fetchone()
        count: int = result[0] if result else 0
        print(f"Database now contains {count} player records")
        
    except Exception as e:
        conn.rollback()
        print(f"Error loading data: {e}")
    finally:
        cursor_obj.close()
        conn.close()
    
    print("\n=== Process Complete ===")

if __name__ == "__main__":
    main()