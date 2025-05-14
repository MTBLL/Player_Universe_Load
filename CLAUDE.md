# Player Universe Load - Setup and Usage Guide

## Configuration Details

### Initial Setup

Before running any scripts, you need to set up the database credentials:

1. Copy the template file to create your secrets file:
   ```bash
   cp scripts/secrets.py.template scripts/secrets.py
   ```

2. Edit the `scripts/secrets.py` file and add your database password:
   ```python
   DB_PASSWORD = "your_database_password_here"
   ```

> **Important**: The `secrets.py` file contains sensitive credentials and is excluded from version control via `.gitignore`. Never commit this file to the repository.

### Database Connection Parameters
- **Host**: mtbl.chigsmi0ar1o.us-west-1.rds.amazonaws.com
- **Port**: 5432 (default)
- **Database Name**: mtbl
- **Username**: mtbl
- **Password**: [stored in secrets.py file - see Initial Setup section]

### Data Source
- **JSON File Path**: `/Users/Shared/BaseballHQ/resources/transform/player_universe_trxd.json`
- **Table Name**: players

## Scripts

All scripts have been moved to the `scripts` directory for better organization. You can use the unified run.py script to execute the main functions:

### Main Script Runner

The `run.py` script provides a unified interface to all tools:

```bash
cd /Users/Shared/BaseballHQ/tools/_load/Player_Universe_Load
source .venv/bin/activate

# Load data
python3 scripts/run.py load

# Verify database
python3 scripts/run.py verify

# Create database
python3 scripts/run.py create-db
```

### Individual Scripts

#### 1. `clean_and_load.py` (Recommended)
The simplest script that drops the existing table and creates a new one with proper structure:
```bash
cd /Users/Shared/BaseballHQ/tools/_load/Player_Universe_Load
source .venv/bin/activate
python3 scripts/clean_and_load.py
```

#### 2. `verify_table.py`
A utility to verify the table structure and query capabilities:
```bash
cd /Users/Shared/BaseballHQ/tools/_load/Player_Universe_Load
source .venv/bin/activate
python3 scripts/verify_table.py
```

#### 3. `test_connection.py`
Script to test database connectivity:
```bash
cd /Users/Shared/BaseballHQ/tools/_load/Player_Universe_Load
source .venv/bin/activate
python3 scripts/test_connection.py
```

#### 4. `create_database.py`
Script to create the mtbl database if it doesn't exist:
```bash
cd /Users/Shared/BaseballHQ/tools/_load/Player_Universe_Load
source .venv/bin/activate
python3 scripts/create_database.py
```

#### 5. `detailed_connection_test.py`
Detailed connection test with specific diagnostics:
```bash
cd /Users/Shared/BaseballHQ/tools/_load/Player_Universe_Load
source .venv/bin/activate
python3 scripts/detailed_connection_test.py
```

## Common Issues and Troubleshooting

### RDS Connectivity Issues
If you encounter connection timeouts:
1. Check that the RDS security group allows connections from your IP address
2. Your current IP address: Check with `curl -s https://api.ipify.org`
3. Add this IP to the security group with port 5432 open

### Data Loading Issues
- For NULL/NOT NULL constraint violations, check the Pydantic model and PostgresLoader
- The current implementation makes all fields nullable for compatibility

## Database Structure
The database contains a `players` table with `id_espn` as the primary key:

### Table Structure
```
Column Name            | Data Type           | Description
--------------------------------------------------------------------------------
id_espn                | integer             | Primary key - ESPN player ID
id_fangraphs           | character varying   | FanGraphs player ID
id_xmlbam              | integer             | MLB MLBAM player ID
name                   | character varying   | Full player name
first_name             | character varying   | Player's first name
last_name              | character varying   | Player's last name
name_nonascii          | character varying   | Name with accents/special characters
name_ascii             | character varying   | Name with ASCII characters only
display_name           | character varying   | Name for display purposes
short_name             | character varying   | Abbreviated name (e.g., "M. Trout")
nickname               | character varying   | Player's nickname if any
slug_espn              | character varying   | URL slug for ESPN
slug_fangraphs         | character varying   | URL slug for FanGraphs
fangraphs_api_route    | character varying   | API route for FanGraphs data
primary_position       | character varying   | Primary fielding position
eligible_slots         | text (JSON array)   | All eligible fantasy positions
pro_team               | character varying   | MLB team abbreviation (e.g., "LAD")
injury_status          | character varying   | Current injury status
status                 | character varying   | Player status (active, etc.)
injured                | boolean             | Whether player is injured
active                 | boolean             | Whether player is active
weight                 | numeric             | Player's weight in pounds
display_weight         | character varying   | Formatted weight string
height                 | integer             | Player's height in inches
display_height         | character varying   | Formatted height string
bats                   | character varying   | Batting handedness
throws                 | character varying   | Throwing handedness
date_of_birth          | character varying   | Player's birth date
birth_place            | jsonb               | Birth place information
debut_year             | integer             | MLB debut year
jersey                 | integer             | Jersey number
headshot               | character varying   | URL to player headshot image
created_at             | timestamp           | Record creation timestamp
```

## Maintenance

### Refreshing Data
To refresh the player data, simply run the `clean_and_load.py` script:
```bash
cd /Users/Shared/BaseballHQ/tools/_load/Player_Universe_Load
source .venv/bin/activate
python3 clean_and_load.py
```

This script will:
1. Drop the existing table
2. Create a new table with the correct structure
3. Load all player data from the JSON file

### Connecting via psql
To connect directly to the database using the PostgreSQL command-line client:
```bash
psql -h mtbl.chigsmi0ar1o.us-west-1.rds.amazonaws.com -p 5432 -d mtbl -U mtbl
```

When prompted, enter your password (found in the `secrets.py` file)

### Useful SQL Queries

```sql
-- Get total player count
SELECT COUNT(*) FROM players;

-- Get players by team
SELECT * FROM players WHERE pro_team = 'LAD' LIMIT 10;

-- Get players by position
SELECT * FROM players WHERE primary_position = 'SS' LIMIT 10;

-- Get players by name
SELECT * FROM players WHERE name ILIKE '%trout%';

-- Get player by ESPN ID
SELECT * FROM players WHERE id_espn = 32267;

-- Get player counts by team
SELECT pro_team, COUNT(*) FROM players GROUP BY pro_team ORDER BY COUNT(*) DESC;
```