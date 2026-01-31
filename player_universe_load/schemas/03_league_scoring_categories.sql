-- League Scoring Categories
DROP TABLE IF EXISTS league_scoring_categories CASCADE;

CREATE TABLE league_scoring_categories (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    stat_type VARCHAR(10) NOT NULL,
    stat_id INTEGER NOT NULL,
    stat_name VARCHAR(20) NOT NULL,
    is_reverse BOOLEAN DEFAULT FALSE,
    sort_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(league_id, stat_type, stat_id)
);

CREATE INDEX idx_scoring_league ON league_scoring_categories(league_id);
CREATE INDEX idx_scoring_type ON league_scoring_categories(stat_type);
