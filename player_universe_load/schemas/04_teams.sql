-- Teams Table
DROP TABLE IF EXISTS teams CASCADE;

CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    team_name VARCHAR(255),
    team_abbrev VARCHAR(10),
    team_logo VARCHAR(500),
    primary_owner VARCHAR(100),
    owners JSONB,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    ties INTEGER DEFAULT 0,
    win_percentage NUMERIC(5,4),
    games_back NUMERIC(5,1),
    budget_spent INTEGER DEFAULT 0,
    budget_remaining INTEGER,
    acquisitions INTEGER DEFAULT 0,
    drops INTEGER DEFAULT 0,
    trades INTEGER DEFAULT 0,
    waiver_rank INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_teams_league ON teams(league_id);
CREATE INDEX idx_teams_owner ON teams(primary_owner);
