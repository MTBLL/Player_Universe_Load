-- Player Valuations
-- Stores fantasy value calculations per player/position/season
-- Two-way players (e.g., Shohei Ohtani) have multiple rows with different positions
DROP TABLE IF EXISTS player_valuations CASCADE;

CREATE TABLE player_valuations (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    primary_position VARCHAR(10) NOT NULL,
    tier VARCHAR(20),
    total_z NUMERIC,
    total_dollars NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season_id, primary_position)
);

CREATE INDEX idx_valuations_player ON player_valuations(player_id);
CREATE INDEX idx_valuations_position ON player_valuations(primary_position);
CREATE INDEX idx_valuations_tier ON player_valuations(tier);
