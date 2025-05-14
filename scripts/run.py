#!/usr/bin/env python3
"""
Helper script to run the Player Universe Load tools
"""
import argparse
import sys
import os
import importlib.util

# Add the parent directory to path so we can import our local modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

def main():
    """Main function to run the appropriate script"""
    parser = argparse.ArgumentParser(
        description="Player Universe Database Loader"
    )
    
    subparsers = parser.add_subparsers(
        dest="command",
        help="Command to execute"
    )
    
    # Load command
    load_parser = subparsers.add_parser(
        "load",
        help="Load player data into the database"
    )
    
    # Verify command
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify the database structure and data"
    )
    
    # Create DB command
    create_db_parser = subparsers.add_parser(
        "create-db",
        help="Create the database if it doesn't exist"
    )
    
    args = parser.parse_args()
    
    # Add scripts directory to the Python path
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    
    # Execute the appropriate command
    if args.command == "load":
        import clean_and_load  # type: ignore
        clean_and_load.main()
    elif args.command == "verify":
        import verify_table  # type: ignore
        verify_table.main()
    elif args.command == "create-db":
        import create_database  # type: ignore
        create_database.main()
    else:
        parser.print_help()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())