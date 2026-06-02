-- Player Savant Metrics
-- Baseball Savant (Statcast) descriptive metric blobs kept as JSONB:
--   statcast, home_runs, sprint_speed, swing_take, expected_statistics.
-- These are one-row-per-player dicts with stable but wide, season-variable
-- key sets — JSONB absorbs Savant's field drift without schema churn. The
-- pitch_arsenal metric is split out into its own typed table
-- (player_pitch_arsenal) because it is a list at a different grain.
--
-- All are OBSERVED stats, not projections — they previously lived in
-- player_projections under projection_source='savant', which mislabeled
-- measured data as forecasts. player_projections is now fangraphs-only.
--
-- sprint_speed is hitter-only and expected_statistics pitcher-only in the
-- source; the absent population simply has no row for that metric.
DROP TABLE IF EXISTS player_savant CASCADE;

CREATE TABLE player_savant (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    metric VARCHAR(50) NOT NULL,
    player_type VARCHAR(10) NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season_id, metric, player_type)
);

CREATE INDEX idx_savant_player ON player_savant(player_id);
CREATE INDEX idx_savant_season ON player_savant(season_id);
CREATE INDEX idx_savant_metric ON player_savant(metric);
