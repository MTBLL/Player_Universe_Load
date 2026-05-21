-- Leagues Table
DROP TABLE IF EXISTS leagues CASCADE;

CREATE TABLE leagues (
    league_id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    league_name VARCHAR(100),
    scoring_period_id INTEGER,
    num_teams INTEGER,
    acquisition_budget INTEGER,
    draft_auction_budget INTEGER,
    roster_settings JSONB,
    -- Games-started limits: the league's pitcher start-cap rule. Flattened
    -- from the trx GamesStartedLimitsModel (one fixed-shape object per
    -- league), so the four scalars become columns rather than JSONB or a
    -- child table. All NULL for leagues with no start cap.
    gsl_stat_id INTEGER,
    gsl_min NUMERIC,
    gsl_max_per_scoring_period NUMERIC,
    gsl_max_per_matchup NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
