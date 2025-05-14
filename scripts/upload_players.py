#!/usr/bin/env python3
"""
Script to upload player universe data to PostgreSQL database
"""
import os
import sys
from player_universe_load.models.player import PlayerModel
from player_universe_load.postgres_loader import PostgresLoader

# Database connection parameters
DB_PARAMS = {
    "host": "mtbl.chigsmi0ar1o.us-west-1.rds.amazonaws.com",
    "port": "5432",
    "dbname": "mtbl",
    "user": "mtbl",
    "password": "cPHVBe5pBpLlgG27l6Sg"
}

# Path to the transformed JSON file
JSON_FILE_PATH = "/Users/Shared/BaseballHQ/resources/transform/player_universe_trxd.json"

# Table name to use in PostgreSQL
TABLE_NAME = "players"

def main():
    """Main function to upload player data to PostgreSQL"""
    # Check if JSON file exists
    if not os.path.exists(JSON_FILE_PATH):
        print(f"Error: JSON file not found at {JSON_FILE_PATH}")
        sys.exit(1)
    
    print(f"Using JSON file: {JSON_FILE_PATH}")
    
    # Initialize the PostgresLoader with database parameters
    try:
        loader = PostgresLoader(DB_PARAMS)
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