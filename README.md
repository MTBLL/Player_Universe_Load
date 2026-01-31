# Player Universe Load

This project loads fantasy baseball data (players, teams, leagues, stats, projections, valuations) into PostgreSQL using a **local-first approach** for fast, efficient database population.

## Overview

The system transforms fixture data from JSON files and loads it into a PostgreSQL database. Instead of directly inserting to a remote database (slow), we:
1. Load to **local PostgreSQL** (30 seconds)
2. Export and upload to **Neon** via `pg_dump` (2-3 minutes)

**Total time: ~3 minutes** (vs 60+ minutes for direct remote loading!)

---

## Quick Start

See **[QUICK_START.md](QUICK_START.md)** for the fastest way to get started.

**TL;DR:**
```bash
# 1. Load to local PostgreSQL (30 seconds)
uv run python scripts/load_local.py

# 2. Export and upload to Neon (2-3 minutes)
bash scripts/export_and_upload.sh
```

---

## What Gets Loaded

From fixture files in `tests/fixtures/`:

- **2,940 players** (1,405 hitters + 1,535 pitchers)
- **17,734 stat records** (batting + pitching, multiple time periods)
- **2,940 projections** (FanGraphs)
- **2,939 valuations** (z-scores, dollar values, tiers)
- **1 league** with 12 scoring categories
- **11 teams** with 258 roster slots
- **110 matchups** (schedule)

---

## Database Schema

**12 normalized tables** designed for Hasura GraphQL:

1. `players` - Player biographical data
2. `leagues` - League configuration
3. `league_scoring_categories` - Scoring rules
4. `teams` - Fantasy teams with records
5. `matchups` - Head-to-head schedule
6. `roster_slots` - Player roster assignments
7. `player_stats_batting` - Batting statistics
8. `player_stats_pitching` - Pitching statistics
9. `player_projections` - FanGraphs projections
10. `player_valuations` - Fantasy valuations (tiers, totals)
11. `player_valuation_details` - Per-category z-scores/dollars
12. `player_fantasy_assignments` - Draft/ownership info

All tables use **foreign keys** for automatic Hasura relationship detection.

See **[docs/postgres_schema_design.md](docs/postgres_schema_design.md)** for complete schema documentation.

---

## Configuration

### Local PostgreSQL
- **Database**: `fantasy_baseball`
- **Connection**: `postgresql://localhost/fantasy_baseball`
- **Install**: `brew install postgresql@18`
- **Start**: `brew services start postgresql@18`

### Neon (Remote)
- **Connection**: Stored in `scripts/secrets.py`
- **Template**: Copy `scripts/secrets.py.template` to `scripts/secrets.py`
- **Add your Neon DATABASE_URL** to the secrets file

### Data Source
- **Fixtures**: `tests/fixtures/*.json`
  - `hitters.json` - 1,405 hitters with stats/projections/valuations
  - `pitchers.json` - 1,535 pitchers with stats/projections/valuations
  - `league_10998_summary.json` - League settings
  - `league_10998_schedule.json` - Schedule/matchups
  - `team_*_roster.json` - Team rosters (11 teams)

---

## Architecture

### Package Structure

```
player_universe_load/          # Main Python package
├── schemas/                   # SQL schema files (01-12)
│   ├── 01_players.sql
│   ├── 02_leagues.sql
│   └── ...
├── loaders/                   # Data loader modules
│   ├── players.py            # Players + stats + projections + valuations
│   ├── leagues.py            # League settings
│   ├── matchups.py           # Schedule
│   └── teams.py              # Teams + rosters
├── db.py                     # Database utilities
└── __main__.py               # Main loader entry point

scripts/                       # Executable scripts
├── load_local.py             # Load to local PostgreSQL
├── export_and_upload.sh      # Export and upload to Neon
├── config.py                 # Configuration
├── secrets.py                # Database credentials (gitignored)
└── verify_table.py           # Verification utilities

tests/fixtures/                # JSON data files
├── hitters.json
├── pitchers.json
├── league_10998_summary.json
├── league_10998_schedule.json
└── team_*_roster.json
```

### Key Components

1. **Schema Files** (`player_universe_load/schemas/`)
   - Numbered 01-12 for execution order
   - Each table in separate file
   - Executed in sequence by `init_schema()`

2. **Loaders** (`player_universe_load/loaders/`)
   - `players.py` - Handles players, stats, projections, valuations
   - `leagues.py` - League settings and scoring categories
   - `matchups.py` - Schedule and matchups
   - `teams.py` - Teams and roster assignments

3. **Database Module** (`player_universe_load/db.py`)
   - `get_connection()` - Get DB connection (respects DATABASE_URL env var)
   - `init_schema()` - Execute all schema files
   - `bulk_insert()` - Efficient bulk inserts with conflict handling
   - `json_serialize()` - JSON field serialization

---

## Usage

### Initial Setup

1. **Install PostgreSQL 18**
   ```bash
   brew install postgresql@18
   brew services start postgresql@18
   ```

2. **Create local database**
   ```bash
   /opt/homebrew/opt/postgresql@18/bin/createdb fantasy_baseball
   ```

3. **Configure Neon credentials**
   ```bash
   cp scripts/secrets.py.template scripts/secrets.py
   # Edit scripts/secrets.py and add your DATABASE_URL
   ```

### Load Data

```bash
# Step 1: Load to local PostgreSQL (30 seconds)
uv run python scripts/load_local.py

# Step 2: Export and upload to Neon (2-3 minutes)
bash scripts/export_and_upload.sh
```

### Verify Data

**Query local database:**
```bash
/opt/homebrew/opt/postgresql@18/bin/psql fantasy_baseball

-- Example queries:
SELECT COUNT(*) FROM players;

SELECT p.name, p.primary_position, s."HR", s."AVG", s."RBI"
FROM players p
JOIN player_stats_batting s ON p.id_espn = s.player_id
WHERE s.stat_period = 'current_season' AND s."HR" > 30
ORDER BY s."HR" DESC;
```

**Verification script:**
```bash
uv run python scripts/verify_table.py
```

---

## Hasura Integration

Once data is loaded to Neon:

1. **Connect Hasura** to your Neon database
2. **Track all tables** in Hasura console
3. **Relationships auto-detected** via foreign keys
4. **Start querying** via GraphQL!

Example query:
```graphql
query TopHomeRunHitters {
  players(
    where: {
      player_stats_batting: {
        stat_period: {_eq: "current_season"}
        HR: {_gt: 30}
      }
    }
    order_by: {player_stats_batting_aggregate: {max: {HR: desc}}}
    limit: 10
  ) {
    name
    primary_position
    pro_team
    player_stats_batting(where: {stat_period: {_eq: "current_season"}}) {
      HR
      AVG
      RBI
      SB
    }
    player_valuations {
      total_dollars
      tier
    }
  }
}
```

---

## Benefits of Local-First Approach

✅ **20x faster** - 3 minutes vs 60 minutes
✅ **Instant iteration** - test schema changes in seconds
✅ **Offline capable** - work without internet
✅ **Easy debugging** - query local DB directly
✅ **Cost efficient** - less Neon compute time
✅ **Production ready** - same data, same schema

---

## Troubleshooting

### PostgreSQL not running
```bash
brew services start postgresql@18
```

### Database doesn't exist
```bash
/opt/homebrew/opt/postgresql@18/bin/createdb fantasy_baseball
```

### Neon connection issues
- Check `scripts/secrets.py` has correct `DATABASE_URL`
- Verify Neon security group allows your IP

### Data validation
```bash
uv run python scripts/verify_table.py
```

---

## Development

### Run tests
```bash
uv run pytest tests/test_load_integration.py -v
```

### Update schema
1. Modify schema files in `player_universe_load/schemas/`
2. Reload local database: `uv run python scripts/load_local.py`
3. Test locally
4. Upload when ready: `bash scripts/export_and_upload.sh`

### Add new data loaders
1. Create loader in `player_universe_load/loaders/`
2. Import and call in `player_universe_load/__main__.py`
3. Test with local database first

---

## License

See project license file.
