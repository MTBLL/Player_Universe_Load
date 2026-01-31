-- Player Fantasy Assignments
DROP TABLE IF EXISTS player_fantasy_assignments CASCADE;

CREATE TABLE player_fantasy_assignments (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    team_id INTEGER REFERENCES teams(team_id) ON DELETE SET NULL,
    season_id INTEGER NOT NULL,
    draft_value NUMERIC,
    draft_round INTEGER,
    draft_pick INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, league_id, season_id)
);

CREATE INDEX idx_fantasy_assign_player ON player_fantasy_assignments(player_id);
CREATE INDEX idx_fantasy_assign_team ON player_fantasy_assignments(team_id);
CREATE INDEX idx_fantasy_assign_league ON player_fantasy_assignments(league_id);
