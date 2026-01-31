# Quick Start - Fast Database Loading

## The Problem
Loading 2,940 players with stats directly to remote Neon database: **~60 minutes** ⏰

## The Solution
Load locally, then export/upload: **~2-3 minutes total** ⚡

---

## One-Command Load & Upload

```bash
# Single command for everything:
uv run player-universe-load load-and-sync
```

**Total time: ~3 minutes** (vs 60 minutes!)

---

## Alternative: Step-by-Step

```bash
# Step 1: Load to local PostgreSQL (30 seconds)
uv run player-universe-load load-local

# Step 2: Sync to Neon (2-3 minutes)
uv run player-universe-load sync-to-neon
```

---

## Initial Setup (One-Time)

### 1. Install PostgreSQL 18

```bash
brew install postgresql@18
brew services start postgresql@18
```

### 2. Create Local Database

```bash
/opt/homebrew/opt/postgresql@18/bin/createdb fantasy_baseball
```

### 3. Configure Neon Credentials

```bash
cp player_universe_load/secrets.py.template player_universe_load/secrets.py
# Edit player_universe_load/secrets.py and add your Neon DATABASE_URL
```

---

## What Gets Loaded

- **2.9k players** (1,405 hitters + 1,535 pitchers)
- **17.7k stat records** (batting + pitching, multiple time periods)
- **2.9k projections**
- **2.9k valuations** with z-scores and dollar values
- **1 league** with 12 scoring categories
- **11 teams** with full rosters (258 roster slots)
- **110 matchups** (schedule)

---

## Database Schema

**12 Tables:**
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

All tables use **foreign keys** for automatic Hasura GraphQL relationships!

---

## Additional Commands

### Verify Database

```bash
uv run player-universe-load verify
```

Shows table counts and sample queries.

### Query Local Database

```bash
/opt/homebrew/opt/postgresql@18/bin/psql fantasy_baseball
```

Example queries:
```sql
-- Player counts
SELECT COUNT(*) FROM players;

-- Top home run hitters
SELECT p.name, s."HR", s."AVG", s."RBI"
FROM players p
JOIN player_stats_batting s ON p.id_espn = s.player_id
WHERE s.stat_period = 'current_season' AND "HR" > 30
ORDER BY s."HR" DESC LIMIT 10;
```

---

## Next Steps

### Connect Hasura

1. Point Hasura at your Neon database
2. Track all tables
3. Relationships auto-detected via foreign keys
4. Start querying!

Example GraphQL query:
```graphql
query {
  players(where: {pro_team: {_eq: "LAD"}}, limit: 10) {
    name
    primary_position
    player_stats_batting(where: {stat_period: {_eq: "current_season"}}) {
      AVG
      HR
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

## How It Works

### Local Load
1. Connects to local PostgreSQL: `postgresql://localhost/fantasy_baseball`
2. Drops and recreates all tables
3. Loads all fixture data from `tests/fixtures/`
4. **Completes in ~30 seconds**

### Sync to Neon
1. Exports local DB to SQL dump (`pg_dump`)
2. Uploads dump to Neon with `psql`
3. Single network operation instead of thousands
4. **Completes in ~2-3 minutes**

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
Check `player_universe_load/secrets.py` has correct `DATABASE_URL`

---

## File Structure

```
player_universe_load/          # Main Python package
├── schemas/                   # 12 SQL schema files
├── loaders/                   # Python data loaders
├── validation/                # Schema validation
├── cli.py                     # CLI commands
├── db.py                      # Database utilities
├── verification.py            # Verification tools
└── secrets.py                 # DB credentials (gitignored)

tests/fixtures/                # JSON data files
├── hitters.json
├── pitchers.json
├── league_10998_summary.json
├── league_10998_schedule.json
└── team_*_roster.json
```

---

## Benefits of Local-First Approach

✅ **20x faster** - 3 minutes vs 60 minutes
✅ **Instant iteration** - test schema changes in seconds
✅ **Offline capable** - work without internet
✅ **Easy debugging** - query local DB directly
✅ **Cost efficient** - less Neon compute time
✅ **Production ready** - same data, same schema

Happy querying! 🚀
