# Player Universe Load

Clean, concise loaders for fantasy baseball data.

## Quick Start

```bash
# Load all data into the database
uv run -m player_universe_load

# Or with python
uv run python -m player_universe_load
```

## What It Does

1. **Drops and recreates** all tables (clean slate)
2. **Loads players** from `tests/fixtures/hitters.json` and `pitchers.json`
   - Player biographical data
   - Current season stats (batting/pitching)
   - ESPN stats (last 7/15/30 days, previous season)
   - Projections
   - Valuations (z-scores, dollar values)
3. **Loads league** from `league_10998_summary.json`
   - League settings
   - Scoring categories
4. **Loads schedule** from `league_10998_schedule.json`
   - All matchups
5. **Loads teams** from `team_*_roster.json` files
   - Team info and records
   - Roster assignments
   - Fantasy player assignments

## Structure

```
player_universe_load/
├── schemas/              # SQL schema files (executed in order)
│   ├── 01_players.sql
│   ├── 02_leagues.sql
│   ├── 03_league_scoring_categories.sql
│   └── ...
├── loaders/             # Data loader modules
│   ├── players.py       # Player, stats, projections, valuations
│   ├── leagues.py       # League settings and scoring
│   ├── matchups.py      # Schedule/matchups
│   └── teams.py         # Teams and rosters
├── db.py                # Database connection and utilities
└── __main__.py          # Main entry point
```

## Database Schema

See `/docs/postgres_schema_design.md` for full schema documentation.

**12 Tables:**
- `players` - Player biographical data
- `leagues` - League configuration
- `league_scoring_categories` - Scoring rules
- `teams` - Fantasy teams
- `matchups` - Head-to-head schedule
- `roster_slots` - Player roster assignments
- `player_stats_batting` - Batting statistics
- `player_stats_pitching` - Pitching statistics
- `player_projections` - Statistical projections
- `player_valuations` - Fantasy valuations
- `player_valuation_details` - Per-category z-scores/dollars
- `player_fantasy_assignments` - Player draft info

## Configuration

Database connection is configured in `scripts/secrets.py`:

```python
DATABASE_URL = "postgresql://user:password@host:port/database"
```

## For Hasura

All tables use foreign keys for automatic relationship detection in Hasura. Once loaded, you can:

1. Point Hasura at your database
2. Track all tables
3. Relationships will be auto-detected
4. Start querying via GraphQL!

Example query:
```graphql
query {
  players(where: {pro_team: {_eq: "LAD"}}) {
    name
    player_stats_batting(where: {stat_period: {_eq: "current_season"}}) {
      AVG, HR, RBI
    }
  }
}
```
