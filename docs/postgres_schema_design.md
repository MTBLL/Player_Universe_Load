# PostgreSQL Schema Design for Fantasy Baseball Data
## Optimized for Hasura GraphQL Integration

## Overview
This schema normalizes the fantasy baseball data into multiple relational tables, designed for efficient querying through Hasura GraphQL. The design follows PostgreSQL best practices and leverages foreign keys for automatic relationship detection in Hasura.

---

## Core Entity Tables

### 1. `players`
Master player table with biographical and basic information.

```sql
CREATE TABLE players (
    -- Primary Keys & Identifiers
    id_espn INTEGER PRIMARY KEY,
    id_fangraphs VARCHAR(20),
    id_xmlbam INTEGER,

    -- Name Information
    name VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    name_ascii VARCHAR(255),
    slug VARCHAR(255),

    -- URLs & Routes
    fangraphs_api_route VARCHAR(500),
    headshot VARCHAR(500),

    -- Position & Team
    primary_position VARCHAR(10),
    eligible_slots JSONB,  -- Array of eligible positions
    pro_team VARCHAR(10),

    -- Physical Attributes
    weight NUMERIC(5,1),
    display_weight VARCHAR(20),
    height INTEGER,  -- in inches
    display_height VARCHAR(10),
    bats VARCHAR(10),
    throws VARCHAR(10),

    -- Birth & Debut
    date_of_birth DATE,
    birth_place JSONB,  -- {city, country}
    debut_year INTEGER,

    -- Status
    injury_status VARCHAR(20),
    status VARCHAR(20),
    injured BOOLEAN,
    active BOOLEAN,
    jersey INTEGER,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    UNIQUE(id_xmlbam),
    UNIQUE(slug)
);

CREATE INDEX idx_players_pro_team ON players(pro_team);
CREATE INDEX idx_players_primary_position ON players(primary_position);
CREATE INDEX idx_players_active ON players(active);
CREATE INDEX idx_players_name ON players(name);
CREATE INDEX idx_players_fangraphs ON players(id_fangraphs);
```

---

### 2. `leagues`
League configuration and settings.

```sql
CREATE TABLE leagues (
    league_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    scoring_period_id INTEGER,
    num_teams INTEGER,
    acquisition_budget INTEGER,
    draft_auction_budget INTEGER,

    -- Roster Settings (stored as JSONB for flexibility)
    roster_settings JSONB,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 3. `league_scoring_categories`
Normalized scoring categories for leagues.

```sql
CREATE TABLE league_scoring_categories (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    stat_type VARCHAR(10) NOT NULL,  -- 'batting' or 'pitching'
    stat_id INTEGER NOT NULL,
    stat_name VARCHAR(20) NOT NULL,
    is_reverse BOOLEAN DEFAULT FALSE,
    sort_order INTEGER,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(league_id, stat_type, stat_id)
);

CREATE INDEX idx_scoring_league ON league_scoring_categories(league_id);
CREATE INDEX idx_scoring_type ON league_scoring_categories(stat_type);
```

---

### 4. `teams`
Fantasy teams within leagues.

```sql
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,

    -- Team Info
    team_name VARCHAR(255),
    team_abbrev VARCHAR(10),
    team_logo VARCHAR(500),
    primary_owner VARCHAR(100),
    owners JSONB,  -- Array of owner IDs

    -- Record
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    ties INTEGER DEFAULT 0,
    win_percentage NUMERIC(5,4),
    games_back NUMERIC(5,1),

    -- Transactions
    budget_spent INTEGER DEFAULT 0,
    budget_remaining INTEGER,
    acquisitions INTEGER DEFAULT 0,
    drops INTEGER DEFAULT 0,
    trades INTEGER DEFAULT 0,
    waiver_rank INTEGER,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(team_id, league_id)
);

CREATE INDEX idx_teams_league ON teams(league_id);
CREATE INDEX idx_teams_owner ON teams(primary_owner);
```

---

### 5. `matchups`
Head-to-head matchups between teams.

```sql
CREATE TABLE matchups (
    matchup_id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    period_id INTEGER NOT NULL,
    is_playoff BOOLEAN DEFAULT FALSE,
    is_bye_week BOOLEAN DEFAULT FALSE,

    -- Team 1
    team1_id INTEGER REFERENCES teams(team_id),
    team1_score VARCHAR(20),  -- Format: "W-L-T"

    -- Team 2 (nullable for bye weeks)
    team2_id INTEGER REFERENCES teams(team_id),
    team2_score VARCHAR(20),

    -- Result
    winner_id INTEGER REFERENCES teams(team_id),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_matchups_league ON matchups(league_id);
CREATE INDEX idx_matchups_period ON matchups(period_id);
CREATE INDEX idx_matchups_team1 ON matchups(team1_id);
CREATE INDEX idx_matchups_team2 ON matchups(team2_id);
CREATE INDEX idx_matchups_playoff ON matchups(is_playoff);
```

---

### 6. `roster_slots`
Player roster assignments for teams.

```sql
CREATE TABLE roster_slots (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,

    -- Player Info
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    lineup_slot VARCHAR(20) NOT NULL,  -- C, 1B, 2B, 3B, SS, OF, UTIL, SP, RP, BENCH, IL

    -- Acquisition
    acquisition_type VARCHAR(20),  -- DRAFT, WAIVER, TRADE, FREE_AGENT
    acquisition_date TIMESTAMP,
    keeper_value INTEGER,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(team_id, player_id, season_id)
);

CREATE INDEX idx_roster_team ON roster_slots(team_id);
CREATE INDEX idx_roster_player ON roster_slots(player_id);
CREATE INDEX idx_roster_slot ON roster_slots(lineup_slot);
CREATE INDEX idx_roster_league ON roster_slots(league_id);
```

---

## Statistics Tables

### 7. `player_stats_current`
Current season statistics (separate tables for hitters and pitchers due to different stat sets).

```sql
CREATE TABLE player_stats_batting (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    stat_period VARCHAR(50) DEFAULT 'current_season',  -- current_season, last_7_games, last_15_games, etc.

    -- Counting Stats
    "G" NUMERIC,
    "AB" NUMERIC,
    "PA" NUMERIC,
    "H" NUMERIC,
    singles NUMERIC,
    doubles NUMERIC,
    triples NUMERIC,
    "HR" NUMERIC,
    "XBH" NUMERIC,
    "TB" NUMERIC,
    "R" NUMERIC,
    "RBI" NUMERIC,
    "SB" NUMERIC,
    "CS" NUMERIC,
    "SBN" NUMERIC,
    "BB" NUMERIC,
    "IBB" NUMERIC,
    "HBP" NUMERIC,
    "SF" NUMERIC,
    "SAC" NUMERIC,
    "SO" NUMERIC,
    "GDP" NUMERIC,

    -- Rate Stats
    "AVG" NUMERIC,
    "OBP" NUMERIC,
    "SLG" NUMERIC,
    "OPS" NUMERIC,
    "BABIP" NUMERIC,
    "ISO" NUMERIC,
    "wOBA" NUMERIC,

    -- Advanced Stats
    exit_velo NUMERIC,
    adj_exit_velo NUMERIC,
    launch_angle NUMERIC,
    attack_angle NUMERIC,
    attack_dir NUMERIC,
    bat_speed NUMERIC,
    swing_length NUMERIC,
    swing_path_tilt NUMERIC,
    swing_miss_pct NUMERIC,
    swings INTEGER,
    takes INTEGER,
    whiffs INTEGER,
    barrel_rate NUMERIC,
    barrels_per_bbe_pct NUMERIC,
    barrels_per_pa_pct NUMERIC,
    barrels_total INTEGER,
    hard_hit_rate NUMERIC,
    hardhit_pct NUMERIC,
    batter_run_value_per_100 NUMERIC,

    -- Expected Stats
    "xAVG" NUMERIC,
    "xOBP" NUMERIC,
    "xSLG" NUMERIC,
    "xwOBA" NUMERIC,
    "xAVGdiff" NUMERIC,
    "xOBPdiff" NUMERIC,
    "xSLGdiff" NUMERIC,

    -- Percentile Rankings
    "BB_pct" NUMERIC,
    "K_pct" NUMERIC,
    "BBdist" INTEGER,
    "Kdist" INTEGER,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(player_id, season_id, stat_period)
);

CREATE INDEX idx_batting_stats_player ON player_stats_batting(player_id);
CREATE INDEX idx_batting_stats_season ON player_stats_batting(season_id);
CREATE INDEX idx_batting_stats_period ON player_stats_batting(stat_period);


CREATE TABLE player_stats_pitching (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    stat_period VARCHAR(50) DEFAULT 'current_season',

    -- Counting Stats
    "GP" NUMERIC,
    "GS" NUMERIC,
    "OUTS" NUMERIC,
    "IP" NUMERIC,
    "TBF" NUMERIC,
    "H" NUMERIC,
    "R" NUMERIC,
    "ER" NUMERIC,
    "HR" NUMERIC,
    "BB" NUMERIC,
    "IBB" NUMERIC,
    "K" NUMERIC,
    "HBP" NUMERIC,
    "WP" NUMERIC,
    "BK" NUMERIC,

    -- Win/Loss
    "W" NUMERIC,
    "L" NUMERIC,
    "WPCT" NUMERIC,
    "QS" NUMERIC,

    -- Saves & Holds
    "SV" NUMERIC,
    "HLD" NUMERIC,
    "SVHD" NUMERIC,
    "SVO" NUMERIC,
    "BLSV" NUMERIC,
    "SV_pct" NUMERIC,

    -- Rate Stats
    "ERA" NUMERIC,
    "WHIP" NUMERIC,
    "OBA" NUMERIC,
    "OOBP" NUMERIC,
    "k_bb_ratio" NUMERIC,
    "k_per_9" NUMERIC,
    "bb_per_9" NUMERIC,

    -- Pitch Metrics
    velo NUMERIC,
    spin_rate NUMERIC,
    eff_min_vel NUMERIC,
    percieved_velo NUMERIC,
    release_extension NUMERIC,
    release_pos_x NUMERIC,
    release_pos_z NUMERIC,
    break_z NUMERIC,
    induced_break_z NUMERIC,
    break_x_arm_side NUMERIC,
    break_x_batter_in NUMERIC,
    arm_angle NUMERIC,

    -- Advanced Stats
    pitcher_run_exp NUMERIC,
    pitcher_run_value_per_100 NUMERIC,
    exit_velo NUMERIC,
    adj_exit_velo NUMERIC,
    launch_angle NUMERIC,
    swing_miss_pct NUMERIC,
    swings INTEGER,
    takes INTEGER,
    whiffs INTEGER,

    -- Expected Stats
    "xAVG" NUMERIC,
    "xOBP" NUMERIC,
    "xSLG" NUMERIC,
    "xwOBA" NUMERIC,
    "xAVGdiff" NUMERIC,
    "xOBPdiff" NUMERIC,
    "xSLGdiff" NUMERIC,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(player_id, season_id, stat_period)
);

CREATE INDEX idx_pitching_stats_player ON player_stats_pitching(player_id);
CREATE INDEX idx_pitching_stats_season ON player_stats_pitching(season_id);
CREATE INDEX idx_pitching_stats_period ON player_stats_pitching(stat_period);
```

---

### 8. `player_projections`
Statistical projections (FanGraphs, Steamer, etc.).

```sql
CREATE TABLE player_projections (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    projection_source VARCHAR(50) DEFAULT 'fangraphs',  -- fangraphs, steamer, zips, etc.
    player_type VARCHAR(10) NOT NULL,  -- 'hitter' or 'pitcher'

    -- Stored as JSONB for flexibility as projection systems vary
    projections JSONB NOT NULL,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(player_id, season_id, projection_source, player_type)
);

CREATE INDEX idx_projections_player ON player_projections(player_id);
CREATE INDEX idx_projections_season ON player_projections(season_id);
CREATE INDEX idx_projections_source ON player_projections(projection_source);
```

---

### 9. `player_valuations`
Fantasy value calculations (z-scores, dollar values, tiers).

```sql
CREATE TABLE player_valuations (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    league_id INTEGER REFERENCES leagues(league_id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,

    -- Valuation Basics
    primary_position VARCHAR(10),
    tier INTEGER,
    total_z NUMERIC,
    total_dollars NUMERIC,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(player_id, league_id, season_id)
);

CREATE INDEX idx_valuations_player ON player_valuations(player_id);
CREATE INDEX idx_valuations_league ON player_valuations(league_id);
CREATE INDEX idx_valuations_tier ON player_valuations(tier);


CREATE TABLE player_valuation_details (
    id SERIAL PRIMARY KEY,
    valuation_id INTEGER NOT NULL REFERENCES player_valuations(id) ON DELETE CASCADE,
    stat_category VARCHAR(20) NOT NULL,  -- HR, RBI, SB, AVG, ERA, etc.
    z_score NUMERIC,
    dollar_value NUMERIC,

    UNIQUE(valuation_id, stat_category)
);

CREATE INDEX idx_valuation_details_valuation ON player_valuation_details(valuation_id);
CREATE INDEX idx_valuation_details_category ON player_valuation_details(stat_category);
```

---

### 10. `player_fantasy_assignments`
Tracks which fantasy team drafted/owns each player.

```sql
CREATE TABLE player_fantasy_assignments (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    team_id INTEGER REFERENCES teams(team_id) ON DELETE SET NULL,
    season_id INTEGER NOT NULL,

    -- Draft Info
    draft_value NUMERIC,  -- Auction value or draft position
    draft_round INTEGER,
    draft_pick INTEGER,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(player_id, league_id, season_id)
);

CREATE INDEX idx_fantasy_assign_player ON player_fantasy_assignments(player_id);
CREATE INDEX idx_fantasy_assign_team ON player_fantasy_assignments(team_id);
CREATE INDEX idx_fantasy_assign_league ON player_fantasy_assignments(league_id);
```

---

## Hasura Configuration Notes

### Automatic Relationships
Hasura will automatically detect the following relationships based on foreign keys:

**Players:**
- `player_stats_batting` (one-to-many)
- `player_stats_pitching` (one-to-many)
- `player_projections` (one-to-many)
- `player_valuations` (one-to-many)
- `roster_slots` (one-to-many)
- `player_fantasy_assignments` (one-to-many)

**Teams:**
- `league` (many-to-one)
- `roster_slots` (one-to-many)
- `matchups_as_team1` (one-to-many)
- `matchups_as_team2` (one-to-many)
- `matchups_as_winner` (one-to-many)

**Leagues:**
- `teams` (one-to-many)
- `matchups` (one-to-many)
- `league_scoring_categories` (one-to-many)

### Custom GraphQL Queries to Set Up

1. **Get Full Player Profile:**
```graphql
query GetPlayer($id_espn: Int!) {
  players_by_pk(id_espn: $id_espn) {
    name
    primary_position
    pro_team
    player_stats_batting(where: {stat_period: {_eq: "current_season"}}) {
      AVG, HR, RBI, SB
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

2. **Get Team Roster with Stats:**
```graphql
query GetTeamRoster($team_id: Int!) {
  teams_by_pk(team_id: $team_id) {
    team_name
    wins, losses, ties
    roster_slots {
      lineup_slot
      player {
        name
        primary_position
        player_stats_batting(where: {stat_period: {_eq: "current_season"}}) {
          AVG, HR, RBI
        }
      }
    }
  }
}
```

3. **Get League Standings:**
```graphql
query LeagueStandings($league_id: Int!) {
  teams(where: {league_id: {_eq: $league_id}}, order_by: {win_percentage: desc}) {
    team_name
    wins
    losses
    ties
    win_percentage
    games_back
  }
}
```

### Permissions Setup in Hasura

Consider these role-based permissions:

1. **Public role:** Read-only access to players, stats, projections
2. **User role:** Read access to their teams, write access to roster moves
3. **Admin role:** Full access to all tables

---

## Data Migration Strategy

### Phase 1: Core Tables
1. Create `players` table
2. Create `leagues` table
3. Create `teams` table

### Phase 2: Relationships
4. Create `league_scoring_categories` table
5. Create `matchups` table
6. Create `roster_slots` table

### Phase 3: Stats & Analysis
7. Create `player_stats_batting` and `player_stats_pitching` tables
8. Create `player_projections` table
9. Create `player_valuations` and `player_valuation_details` tables
10. Create `player_fantasy_assignments` table

### Loading Order
1. Load leagues first
2. Load players
3. Load teams
4. Load scoring categories, matchups
5. Load roster assignments
6. Load statistics (can be parallelized)
7. Load projections and valuations

---

## Benefits of This Design

### For Hasura GraphQL:
- **Automatic relationship detection** through foreign keys
- **Efficient nested queries** without N+1 problems
- **Flexible filtering** on any indexed column
- **Real-time subscriptions** for live stat updates
- **Row-level security** can be easily configured

### For PostgreSQL:
- **Normalized structure** reduces data duplication
- **Proper indexing** for fast queries
- **Type safety** with appropriate data types
- **JSONB fields** for flexible, varying data structures
- **Cascade deletes** maintain referential integrity

### Query Performance:
- **Separate stat tables** prevent massive JOIN operations
- **Indexed foreign keys** for fast relationship traversal
- **Materialized views** can be added for complex aggregations
- **Partitioning** possible on season_id for historical data

---

## Additional Recommendations

### 1. Materialized Views
Create materialized views for common queries:

```sql
CREATE MATERIALIZED VIEW player_current_stats AS
SELECT
    p.id_espn,
    p.name,
    p.primary_position,
    p.pro_team,
    b."AVG", b."HR", b."RBI", b."SB",
    pv.total_dollars,
    pv.tier
FROM players p
LEFT JOIN player_stats_batting b ON p.id_espn = b.player_id
    AND b.stat_period = 'current_season'
LEFT JOIN player_valuations pv ON p.id_espn = pv.player_id;

CREATE INDEX idx_player_current_stats_position ON player_current_stats(primary_position);
CREATE INDEX idx_player_current_stats_team ON player_current_stats(pro_team);
```

### 2. Computed Fields in Hasura
Add computed fields for:
- Player age (from date_of_birth)
- Fantasy points based on league scoring
- Positional rankings

### 3. Aggregations
Set up aggregation functions in Hasura for:
- League-wide stat leaders
- Team totals
- Position averages

### 4. Historical Data
Consider partitioning tables by `season_id` if storing multiple years:

```sql
CREATE TABLE player_stats_batting_2025 PARTITION OF player_stats_batting
FOR VALUES FROM (2025) TO (2026);
```

---

## Next Steps

1. Review and approve this schema design
2. Create SQL migration scripts for each table
3. Write Python loader scripts to transform JSON → SQL
4. Set up Hasura and configure relationships
5. Test GraphQL queries
6. Configure permissions and authentication
