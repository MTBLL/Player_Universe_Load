-- Player Projections
-- Stores projection blobs (fangraphs preseason/updated/ros) and complex Savant
-- buckets (statcast, home_runs, sprint_speed, swing_take, pitch_arsenal,
-- expected_statistics) as JSONB. Heterogeneous shape -> JSONB is correct fit.
DROP TABLE IF EXISTS player_projections CASCADE;

CREATE TABLE player_projections (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    projection_source VARCHAR(50) NOT NULL,
    projection_period VARCHAR(50) NOT NULL DEFAULT 'preseason',
    player_type VARCHAR(10) NOT NULL,
    projections JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season_id, projection_source, projection_period, player_type)
);

CREATE INDEX idx_projections_player ON player_projections(player_id);
CREATE INDEX idx_projections_season ON player_projections(season_id);
CREATE INDEX idx_projections_source ON player_projections(projection_source);
CREATE INDEX idx_projections_period ON player_projections(projection_period);
