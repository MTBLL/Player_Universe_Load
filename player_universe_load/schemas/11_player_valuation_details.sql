-- Player Valuation Details
DROP TABLE IF EXISTS player_valuation_details CASCADE;

CREATE TABLE player_valuation_details (
    id SERIAL PRIMARY KEY,
    valuation_id INTEGER NOT NULL REFERENCES player_valuations(id) ON DELETE CASCADE,
    stat_category VARCHAR(20) NOT NULL,
    z_score NUMERIC,
    dollar_value NUMERIC,
    UNIQUE(valuation_id, stat_category)
);

CREATE INDEX idx_valuation_details_valuation ON player_valuation_details(valuation_id);
CREATE INDEX idx_valuation_details_category ON player_valuation_details(stat_category);
