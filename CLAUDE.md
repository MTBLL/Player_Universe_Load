# Player Universe Load - Setup and Usage Guide

## Quick Start

**Fast local-first loading workflow:**

```bash
# 1. Load to local PostgreSQL (30 seconds)
uv run player-universe-load load-local

# 2. Export and upload to Neon (2-3 minutes)
uv run player-universe-load sync-to-neon
```

**Total time: ~3 minutes** (vs 60+ minutes for direct remote loading!)

See **[QUICK_START.md](QUICK_START.md)** for detailed instructions.

---

## Configuration Details

### Local PostgreSQL Setup

**Install and start PostgreSQL 18:**
```bash
brew install postgresql@18
brew services start postgresql@18
```

**Create local database:**
```bash
/opt/homebrew/opt/postgresql@18/bin/createdb fantasy_baseball
```

**Connection:**
- **Host**: localhost
- **Port**: 5432 (default)
- **Database Name**: fantasy_baseball
- **Connection String**: `postgresql://localhost/fantasy_baseball`

### Neon (Remote) Setup

**Copy template and configure:**
```bash
cp player_universe_load/secrets.py.template player_universe_load/secrets.py
# Edit player_universe_load/secrets.py and add your Neon DATABASE_URL
```

**Connection parameters (stored in `player_universe_load/secrets.py`):**
```python
DATABASE_URL = "postgresql://user:password@host/database"
```

### Data Source

**Fixture files in** `tests/fixtures/`:
- `hitters.json` - 1,405 hitters with full stats
- `pitchers.json` - 1,535 pitchers with full stats
- `league_10998_summary.json` - League configuration
- `league_10998_schedule.json` - Matchups/schedule
- `team_*_roster.json` - 11 team rosters

---

## Commands

All functionality is available through the unified CLI.

### Main Workflow Commands

#### 1. `load-and-sync` (Recommended)
Full workflow: load locally and sync to Neon in one command.

```bash
uv run player-universe-load load-and-sync
```

**What it does:**
- Loads all data to local PostgreSQL
- Exports local database with `pg_dump`
- Uploads to Neon with `psql`
- **Total time: ~3 minutes**

#### 2. `load-local`
Loads all data to local PostgreSQL database only.

```bash
uv run player-universe-load load-local
```

**What it does:**
- Connects to `postgresql://localhost/fantasy_baseball`
- Validates data schema against database schema
- Drops and recreates all 12 tables
- Loads players, stats, projections, valuations
- Loads league, teams, matchups, rosters
- Shows real-time progress
- **Completes in ~30 seconds**

#### 3. `sync-to-neon`
Exports local database and uploads to Neon.

```bash
uv run player-universe-load sync-to-neon
```

**What it does:**
- Uses `pg_dump --clean --if-exists` to export local database
- Creates `/tmp/fantasy_baseball_dump.sql` (~10MB)
- Reads Neon DATABASE_URL from `player_universe_load/secrets.py`
- Uses `psql` to restore dump to Neon
- Cleans up temporary dump file
- **Completes in ~2-3 minutes**

### Utility Commands

#### 4. `verify`
Verify database structure and query capabilities.

```bash
uv run player-universe-load verify
```

Shows:
- Table structure (columns, types)
- Sample queries
- Player counts by team/position

---

## Database Structure

### Tables (12 total)

All tables have foreign keys for Hasura auto-relationship detection.

**Core entities:**
1. **players** - Player biographical data
   - Primary key: `id_espn`
   - Indexes: name, position, team, active status

2. **leagues** - League configuration
   - Primary key: `league_id`

3. **teams** - Fantasy teams with records
   - Primary key: `team_id`
   - Foreign key: `league_id` → leagues

4. **matchups** - Head-to-head schedule
   - Primary key: `matchup_id`
   - Foreign keys: `league_id`, `team1_id`, `team2_id`, `winner_id`

**Roster management:**
5. **roster_slots** - Player assignments to team positions
   - Foreign keys: `team_id`, `player_id`, `league_id`

6. **league_scoring_categories** - League scoring rules
   - Foreign key: `league_id`

7. **player_fantasy_assignments** - Draft/ownership info
   - Foreign keys: `player_id`, `league_id`, `team_id`

**Statistics:**
8. **player_stats_batting** - Batting statistics
   - Foreign key: `player_id`
   - Unique: (player_id, season_id, stat_period)
   - ~66 stat columns (AVG, HR, RBI, SB, etc.)

9. **player_stats_pitching** - Pitching statistics
   - Foreign key: `player_id`
   - Unique: (player_id, season_id, stat_period)
   - ~70 stat columns (ERA, WHIP, K, SV, etc.)

**Analytics:**
10. **player_projections** - FanGraphs projections
    - Foreign key: `player_id`
    - Stored as JSONB for flexibility

11. **player_valuations** - Fantasy value calculations
    - Foreign keys: `player_id`, `league_id` (optional)

12. **player_valuation_details** - Per-category z-scores/dollars
    - Foreign key: `valuation_id`

### Key Schema Features

**JSONB fields for flexibility:**
- `eligible_slots` - Array of eligible positions
- `birth_place` - Structured location data
- `projections` - Full projection data from different systems
- `roster_settings` - League-specific configurations

**Proper indexing:**
- Primary keys on all tables
- Foreign key indexes for joins
- Commonly queried fields (position, team, name)

**Data integrity:**
- Foreign key constraints with CASCADE/SET NULL
- Unique constraints where needed
- NOT NULL on critical fields only

---

## Common Issues and Troubleshooting

### PostgreSQL Issues

**PostgreSQL not running:**
```bash
brew services start postgresql@18
```

**Database doesn't exist:**
```bash
/opt/homebrew/opt/postgresql@18/bin/createdb fantasy_baseball
```

**Check if PostgreSQL is listening:**
```bash
/opt/homebrew/opt/postgresql@18/bin/psql -l
```

### Neon Connection Issues

**Check secrets file exists:**
```bash
cat player_universe_load/secrets.py
# Should show: DATABASE_URL = "postgresql://..."
```

**Test Neon connection:**
```bash
psql "$DATABASE_URL" -c "SELECT version();"
```

**Security group:** Verify Neon allows connections from your IP

### Data Loading Issues

**Constraint violations:**
- Check fixture data for missing required fields
- Verify foreign key relationships (teams before matchups, etc.)
- Check for duplicate primary keys

**Slow loading:**
- Local load should be ~30 seconds
- If slower, check PostgreSQL is running locally (not connecting to remote)
- Check DATABASE_URL environment variable

---

## Database Queries

### Connect to Local Database

```bash
/opt/homebrew/opt/postgresql@18/bin/psql fantasy_baseball
```

### Useful SQL Queries

**Player counts:**
```sql
SELECT COUNT(*) FROM players;
SELECT COUNT(*) FROM player_stats_batting;
SELECT COUNT(*) FROM player_stats_pitching;
```

**Top home run hitters:**
```sql
SELECT p.name, p.pro_team, s."HR", s."AVG", s."RBI"
FROM players p
JOIN player_stats_batting s ON p.id_espn = s.player_id
WHERE s.stat_period = 'current_season' AND s."HR" > 30
ORDER BY s."HR" DESC
LIMIT 10;
```

**Top strikeout pitchers:**
```sql
SELECT p.name, p.pro_team, s."K", s."ERA", s."WHIP"
FROM players p
JOIN player_stats_pitching s ON p.id_espn = s.player_id
WHERE s.stat_period = 'current_season' AND s."K" > 200
ORDER BY s."K" DESC
LIMIT 10;
```

**Team rosters:**
```sql
SELECT t.team_name, COUNT(r.player_id) as roster_size
FROM teams t
LEFT JOIN roster_slots r ON t.team_id = r.team_id
GROUP BY t.team_id, t.team_name
ORDER BY roster_size DESC;
```

**Player valuations:**
```sql
SELECT p.name, v.total_dollars, v.tier, v.primary_position
FROM players p
JOIN player_valuations v ON p.id_espn = v.player_id
WHERE v.total_dollars > 30
ORDER BY v.total_dollars DESC
LIMIT 20;
```

**League standings:**
```sql
SELECT team_name, wins, losses, ties, win_percentage, games_back
FROM teams
ORDER BY win_percentage DESC;
```

---

## Maintenance

### Refreshing Data

To refresh with updated fixture data:

```bash
# 1. Update fixture JSON files in tests/fixtures/

# 2. Reload local database
uv run player-universe-load load-local

# 3. Verify locally
/opt/homebrew/opt/postgresql@18/bin/psql fantasy_baseball

# 4. Upload to Neon when ready
uv run player-universe-load sync-to-neon
```

### Schema Changes

To modify the database schema:

```bash
# 1. Edit schema files in player_universe_load/schemas/

# 2. Test locally
uv run player-universe-load load-local

# 3. Query and verify changes
/opt/homebrew/opt/postgresql@18/bin/psql fantasy_baseball

# 4. Upload to Neon when satisfied
uv run player-universe-load sync-to-neon
```

### Backup Local Database

```bash
/opt/homebrew/opt/postgresql@18/bin/pg_dump fantasy_baseball > backup_$(date +%Y%m%d).sql
```

### Restore from Backup

```bash
/opt/homebrew/opt/postgresql@18/bin/psql fantasy_baseball < backup_20260130.sql
```

---

## Benefits of Local-First Workflow

✅ **20x faster** - 3 minutes total vs 60+ minutes direct remote
✅ **Instant iteration** - test schema changes in seconds locally
✅ **Offline capable** - work without internet connection
✅ **Easy debugging** - query local DB directly with psql
✅ **Cost efficient** - minimize Neon compute time
✅ **Production ready** - same data, same schema, same result

---

## Next Steps

### Connect Hasura to Neon

1. **Get Neon connection string** from `player_universe_load/secrets.py`
2. **Add to Hasura** as new PostgreSQL data source
3. **Track all tables** in Hasura console
4. **Relationships auto-detected** via foreign keys
5. **Start querying** with GraphQL!

### Example Hasura GraphQL Query

```graphql
query GetTopPlayers {
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
    roster_slots {
      team {
        team_name
      }
    }
  }
}
```

---

## Development Workflow

### For Schema Changes

1. Edit `player_universe_load/schemas/*.sql`
2. Run `uv run player-universe-load load-local`
3. Test queries locally
4. Run `uv run player-universe-load sync-to-neon` when ready

### For Data Loader Changes

1. Edit files in `player_universe_load/loaders/`
2. Run `uv run player-universe-load load-local`
3. Verify data loaded correctly
4. Run integration tests: `uv run pytest tests/test_load_integration.py -v`
5. Upload to Neon when ready

### For New Fixture Data

1. Update JSON files in `tests/fixtures/`
2. Run `uv run player-universe-load load-local`
3. Verify new data appears
4. Upload to Neon: `uv run player-universe-load sync-to-neon`

---

## File Organization

```
Player_Universe_Load/
├── player_universe_load/       # Main Python package
│   ├── schemas/                # SQL schema files (01-12)
│   ├── loaders/                # Data loaders
│   ├── validation/             # Schema validation
│   ├── cli.py                  # CLI commands
│   ├── db.py                   # Database utilities
│   ├── verification.py         # Database verification
│   ├── __main__.py             # Entry point
│   └── secrets.py              # DB credentials (gitignored)
├── tests/
│   ├── fixtures/               # JSON data files
│   └── test_load_integration.py
├── docs/
│   └── postgres_schema_design.md
├── README.md                   # Main documentation
├── QUICK_START.md              # Quick reference
└── CLAUDE.md                   # This file
```

---

For the absolute fastest start, see **[QUICK_START.md](QUICK_START.md)**.

For detailed architecture info, see **[README.md](README.md)**.

For schema details, see **[docs/postgres_schema_design.md](docs/postgres_schema_design.md)**.
