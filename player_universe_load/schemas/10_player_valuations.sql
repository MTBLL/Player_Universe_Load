-- Player Valuations
-- Stores fantasy value calculations per player/position/season/scenario.
-- valuation_type discriminates between scenarios: preseason, updated, ros, synthetic, current.
-- Two-way players (e.g., Shohei Ohtani) have multiple rows with different positions.
DROP TABLE IF EXISTS player_valuations CASCADE;

CREATE TABLE player_valuations (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    valuation_type VARCHAR(20) NOT NULL,
    primary_position VARCHAR(10) NOT NULL,
    tier VARCHAR(20),
    total_z NUMERIC,
    total_dollars NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season_id, primary_position, valuation_type)
);

CREATE INDEX idx_valuations_player ON player_valuations(player_id);
CREATE INDEX idx_valuations_position ON player_valuations(primary_position);
CREATE INDEX idx_valuations_tier ON player_valuations(tier);
CREATE INDEX idx_valuations_type ON player_valuations(valuation_type);
