-- Matchup Categories Table
-- Per-category result breakdown for each team in a matchup. One row per
-- (matchup, team, category). Mirrors the player_valuations ->
-- player_valuation_details split: a child table normalizing the repeating
-- category records that arrive nested in the schedule JSON.
-- Bye-week matchups carry a single sentinel row (category = 'BYE').
DROP TABLE IF EXISTS matchup_categories CASCADE;

CREATE TABLE matchup_categories (
    id SERIAL PRIMARY KEY,
    matchup_id INTEGER NOT NULL REFERENCES matchups(matchup_id) ON DELETE CASCADE,
    team_id INTEGER REFERENCES teams(team_id),
    category VARCHAR(20) NOT NULL,
    value NUMERIC,
    result VARCHAR(10),
    UNIQUE(matchup_id, team_id, category)
);

CREATE INDEX idx_matchup_categories_matchup ON matchup_categories(matchup_id);
CREATE INDEX idx_matchup_categories_team ON matchup_categories(team_id);
CREATE INDEX idx_matchup_categories_category ON matchup_categories(category);
