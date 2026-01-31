-- Leagues Table
DROP TABLE IF EXISTS leagues CASCADE;

CREATE TABLE leagues (
    league_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    scoring_period_id INTEGER,
    num_teams INTEGER,
    acquisition_budget INTEGER,
    draft_auction_budget INTEGER,
    roster_settings JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
