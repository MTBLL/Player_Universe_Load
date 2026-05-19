[![codecov](https://codecov.io/gh/MTBLL/Player_Universe_Load/graph/badge.svg?token=FQid9UjEFi)](https://codecov.io/gh/MTBLL/Player_Universe_Load)

# Player Universe Load

This project loads fantasy baseball data (players, teams, leagues, stats, projections, valuations) into PostgreSQL using a **local-first approach** for fast, efficient database population.

## Overview

The system transforms fixture data from JSON files and emits **three** output artifacts:
1. Load to **local PostgreSQL** (30 seconds) — fast queries during pipeline runs
2. Export **parquet files** to `/Users/Shared/BaseballHQ/resources/analytics/` (~3 seconds) — columnar artifact for downstream viz/notebook consumption via DuckDB / Polars / Pandas / Arrow
3. Export and upload to **Neon** via `pg_dump` (2-3 minutes) — durable remote copy, queryable via Hasura GraphQL

**Total time: ~3 minutes** (vs 60+ minutes for direct remote loading!)

---

## Quick Start

See **[QUICK_START.md](QUICK_START.md)** for the fastest way to get started.

**TL;DR:**
```bash
# Run all three steps in one command
uv run player-universe-load load-and-sync

# Or step by step:
uv run player-universe-load load-local         # local Postgres
uv run player-universe-load export-parquets    # /Users/Shared/BaseballHQ/resources/analytics/*.parquet
uv run player-universe-load sync-to-neon       # remote Neon
```

---

## What Gets Loaded

Production volumes (ETL pipeline output read from
`/Users/Shared/BaseballHQ/resources/{load,transform}/`):

- **~3,400 players** (~1,640 hitters + ~1,770 pitchers)
- **~21,000 stat records** (batting + pitching across 9 stat periods:
  ESPN proj/current/previous/last_7/last_15/last_30 + Savant all/vs_r/vs_l)
- **~12,000 projections** (Fangraphs preseason/updated/ros + Savant blobs)
- **~10,000 valuations** across 5 scenarios (preseason/updated/ros/synthetic/current)
- **1 league** with 12 scoring categories
- **12 teams** with ~290 roster slots
- **84 matchups** (schedule)

`tests/fixtures/` holds a slim 200-player sample (deterministic seed) used by
CI; production data lives outside the repo.

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
- **Connection**: Stored in `player_universe_load/secrets.py`
- **Template**: Copy `player_universe_load/secrets.py.template` to `player_universe_load/secrets.py`
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
├── exporters/                 # Output artifact emitters
│   └── parquet.py            # Postgres → parquet for downstream analytics
├── validation/                # Schema validation
│   └── schema_validator.py   # Validate data vs DB schema
├── cli.py                     # CLI commands
├── db.py                      # Database utilities
├── verification.py            # Database verification
├── __main__.py                # Main loader entry point
└── secrets.py                 # Database credentials (gitignored)

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
   cp player_universe_load/secrets.py.template player_universe_load/secrets.py
   # Edit player_universe_load/secrets.py and add your DATABASE_URL
   ```

### Load Data

```bash
# All three artifacts (local Postgres + parquets + Neon)
uv run player-universe-load load-and-sync

# Or step-by-step:
uv run player-universe-load load-local         # local Postgres (30s)
uv run player-universe-load export-parquets    # parquet files (~3s)
uv run player-universe-load sync-to-neon       # Neon (2-3 min)
```

### Query parquets

```bash
duckdb -c "SELECT name, primary_position FROM read_parquet('/Users/Shared/BaseballHQ/resources/analytics/players.parquet') LIMIT 5"
```

JSONB columns (e.g. `eligible_slots`, `birth_place`, `projections`) are stored
as JSON strings in parquet — pyarrow type-inference doesn't accept the
heterogeneous nested shapes that JSONB permits. Readers should `json.loads()`
those columns to recover structure (DuckDB: `json_extract`).

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
uv run player-universe-load verify
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
- Check `player_universe_load/secrets.py` has correct `DATABASE_URL`
- Verify Neon security group allows your IP

### Data validation
```bash
uv run player-universe-load verify
```

---

## Development

### Run tests
```bash
uv run pytest tests/ -v
# Or one file:
uv run pytest tests/test_load_integration.py -v
uv run pytest tests/test_parquet_export.py -v
```

### Update schema
1. Modify schema files in `player_universe_load/schemas/`
2. Reload local database: `uv run player-universe-load load-local`
3. Test locally
4. Upload when ready: `uv run player-universe-load sync-to-neon`

### Add new data loaders
1. Create loader in `player_universe_load/loaders/`
2. Import and call in `player_universe_load/__main__.py`
3. Test with local database first

---

## License

See project license file.
