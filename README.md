# Player Universe Load

This project loads a local transformed Player Universe (combined ESPN + Fangraphs) from JSON and uploads it as a PostgreSQL database hosted by AWS RDS.

## Overview

The Player Universe Load system takes player data from a transformed JSON file and uploads it to an AWS RDS PostgreSQL database. The system uses Pydantic models for data validation and handles the creation of database tables and data insertion.

## Configuration

### Database Connection
- **Host**: mtbl.chigsmi0ar1o.us-west-1.rds.amazonaws.com
- **Port**: 5432 (default)
- **Database**: mtbl
- **User**: mtbl

### Data Source
- **JSON Path**: `/Users/Shared/BaseballHQ/resources/transform/player_universe_trxd.json`
- **Target Table**: players

## Usage

### Setup
Make sure you have Python and the required dependencies installed:
```bash
# Activate the virtual environment
source .venv/bin/activate
```

### Running the Upload
To upload the player data to PostgreSQL:
```bash
# Run the clean_and_load script
cd /Users/Shared/BaseballHQ/tools/_load/Player_Universe_Load
source .venv/bin/activate
python3 scripts/run.py load
```

### Additional Utilities
All scripts have been moved to the `scripts` directory for better organization:

```bash
# Verify database and table structure
python3 scripts/run.py verify

# Create the database if it doesn't exist
python3 scripts/run.py create-db
```

Additional helper scripts:
- `scripts/test_connection.py`: Test database connectivity
- `scripts/detailed_connection_test.py`: Detailed connection testing with diagnostics
- `scripts/check_schema.py`: Check database schema and optionally drop tables

## Implementation Details

### Key Components
1. **PlayerModel**: Pydantic model defining the player data structure
2. **PostgresLoader**: Class for handling database connections and data loading

### Database Schema
The database uses a straightforward schema with the following key aspects:
- `id_espn` is used as the primary key
- All other fields are nullable for flexibility
- Special handling for JSON fields (eligible_slots, birth_place)

### Process
1. Reads player data from the JSON file
2. Creates a PostgreSQL table with `id_espn` as primary key
3. Validates and transforms the data
4. Uploads the data to the PostgreSQL database

### Security
- RDS instance must have security group rules to allow connections from your IP
- Connection uses standard PostgreSQL authentication

## PostgreSQL Access
To connect directly to the database with psql:
```bash
psql -h mtbl.chigsmi0ar1o.us-west-1.rds.amazonaws.com -p 5432 -d mtbl -U mtbl
```

Then run queries like:
```sql
-- Get players by team
SELECT name, primary_position FROM players WHERE pro_team = 'LAD' LIMIT 5;

-- Get player counts by position
SELECT primary_position, COUNT(*) FROM players 
GROUP BY primary_position ORDER BY COUNT(*) DESC;
```

## Troubleshooting
See the CLAUDE.md file for detailed troubleshooting information, common issues and useful SQL queries.
