#!/usr/bin/env python3
"""
Main entry point for the Player Universe Load package
"""

import argparse
import sys
from typing import List

try:
    from . import clean_and_load, create_database, verify_table
except ImportError:
    import clean_and_load  # type: ignore
    import create_database  # type: ignore
    import verify_table  # type: ignore


def main(args: List[str] | None = None) -> int:
    """Process command line arguments and run the appropriate function"""
    parser = argparse.ArgumentParser(description="Player Universe Database Loader")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Load command
    subparsers.add_parser("load", help="Load player data into the database")

    # Verify command
    subparsers.add_parser("verify", help="Verify the database structure and data")

    # Create DB command
    subparsers.add_parser("create-db", help="Create the database if it doesn't exist")

    parsed_args = parser.parse_args(args if args is not None else [])

    # Execute the appropriate command
    if parsed_args.command == "load":
        clean_and_load.main()
    elif parsed_args.command == "verify":
        verify_table.main()
    elif parsed_args.command == "create-db":
        create_database.main()
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
