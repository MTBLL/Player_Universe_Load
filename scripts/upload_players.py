#!/usr/bin/env python3
"""
Script to upload player universe data to PostgreSQL database
"""
import os
import sys
from player_universe_load.models.player import PlayerModel
from player_universe_load.postgres_loader import PostgresLoader

try:
    from .config import DATABASE_URL, JSON_FILE_PATH
except ImportError:
    from config import DATABASE_URL, JSON_FILE_PATH  # type: ignore

# Table name to use in PostgreSQL
TABLE_NAME = "players"

def main():
    """Main function to upload player data to PostgreSQL"""
    # Check if JSON file exists
    if not os.path.exists(JSON_FILE_PATH):
        print(f"Error: JSON file not found at {JSON_FILE_PATH}")
        sys.exit(1)
    
    print(f"Using JSON file: {JSON_FILE_PATH}")
    
    # Initialize the PostgresLoader with connection string
    try:
        loader = PostgresLoader(connection_string=DATABASE_URL)
        print("PostgresLoader initialized successfully")
        
        # Test connection
        print("Testing database connection...")
        conn = loader.get_connection()
        conn.close()
        print("Database connection successful")
        
        # Load data
        print(f"Loading player data into {TABLE_NAME} table...")
        loader.load_validated_json(JSON_FILE_PATH, PlayerModel, TABLE_NAME)
        print("Data upload completed successfully")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()