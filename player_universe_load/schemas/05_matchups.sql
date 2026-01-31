-- Matchups Table
DROP TABLE IF EXISTS matchups CASCADE;

CREATE TABLE matchups (
    matchup_id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    period_id INTEGER NOT NULL,
    is_playoff BOOLEAN DEFAULT FALSE,
    is_bye_week BOOLEAN DEFAULT FALSE,
    team1_id INTEGER REFERENCES teams(team_id),
    team1_score VARCHAR(20),
    team2_id INTEGER REFERENCES teams(team_id),
    team2_score VARCHAR(20),
    winner_id INTEGER REFERENCES teams(team_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_matchups_league ON matchups(league_id);
CREATE INDEX idx_matchups_period ON matchups(period_id);
CREATE INDEX idx_matchups_team1 ON matchups(team1_id);
CREATE INDEX idx_matchups_team2 ON matchups(team2_id);
CREATE INDEX idx_matchups_playoff ON matchups(is_playoff);
