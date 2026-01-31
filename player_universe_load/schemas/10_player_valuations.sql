-- Player Valuations
DROP TABLE IF EXISTS player_valuations CASCADE;

CREATE TABLE player_valuations (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    league_id INTEGER REFERENCES leagues(league_id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    primary_position VARCHAR(10),
    tier VARCHAR(20),
    total_z NUMERIC,
    total_dollars NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, league_id, season_id)
);

CREATE INDEX idx_valuations_player ON player_valuations(player_id);
CREATE INDEX idx_valuations_league ON player_valuations(league_id);
CREATE INDEX idx_valuations_tier ON player_valuations(tier);
