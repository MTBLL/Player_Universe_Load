-- Player Pitch Arsenal
-- Baseball Savant pitch-arsenal data, fully unwrapped from the source
-- stats.savant.pitch_arsenal list into one typed row per (player, pitch_type).
-- player_type distinguishes pitches THROWN (pitcher) from pitches FACED
-- (hitter); both share an identical 32-field schema. Observed data, not a
-- projection — this previously lived (un-typed) in player_projections under
-- projection_source='savant', projection_period='pitch_arsenal'.
DROP TABLE IF EXISTS player_pitch_arsenal CASCADE;

CREATE TABLE player_pitch_arsenal (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    player_type VARCHAR(10) NOT NULL,
    pitch_type VARCHAR(10) NOT NULL,
    pitch_name VARCHAR(40),
    pitches INTEGER,
    pitch_usage_pct NUMERIC,
    "PA" INTEGER,
    "AVG" NUMERIC,
    "SLG" NUMERIC,
    "wOBA" NUMERIC,
    "xAVG" NUMERIC,
    "xSLG" NUMERIC,
    "xwOBA" NUMERIC,
    "K_pct" NUMERIC,
    whiff_pct NUMERIC,
    put_away_pct NUMERIC,
    hardhit_pct NUMERIC,
    run_value INTEGER,
    run_value_per_100 NUMERIC,
    -- Savant percentile ranks (0-100) for each metric above.
    pitches_pct_rnk NUMERIC,
    pitch_usage_pct_pct_rnk NUMERIC,
    "PA_pct_rnk" NUMERIC,
    "AVG_pct_rnk" NUMERIC,
    "SLG_pct_rnk" NUMERIC,
    "wOBA_pct_rnk" NUMERIC,
    "xAVG_pct_rnk" NUMERIC,
    "xSLG_pct_rnk" NUMERIC,
    "xwOBA_pct_rnk" NUMERIC,
    "K_pct_pct_rnk" NUMERIC,
    whiff_pct_pct_rnk NUMERIC,
    put_away_pct_pct_rnk NUMERIC,
    hardhit_pct_pct_rnk NUMERIC,
    run_value_pct_rnk NUMERIC,
    run_value_per_100_pct_rnk NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season_id, player_type, pitch_type)
);

CREATE INDEX idx_pitch_arsenal_player ON player_pitch_arsenal(player_id);
CREATE INDEX idx_pitch_arsenal_season ON player_pitch_arsenal(season_id);
CREATE INDEX idx_pitch_arsenal_pitch_type ON player_pitch_arsenal(pitch_type);
