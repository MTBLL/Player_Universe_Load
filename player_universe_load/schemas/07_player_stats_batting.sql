-- Player Stats - Batting
DROP TABLE IF EXISTS player_stats_batting CASCADE;

CREATE TABLE player_stats_batting (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    stat_period VARCHAR(50) DEFAULT 'current_season',
    "G" NUMERIC, "AB" NUMERIC, "PA" NUMERIC, "H" NUMERIC,
    singles NUMERIC, doubles NUMERIC, triples NUMERIC, "HR" NUMERIC,
    "XBH" NUMERIC, "TB" NUMERIC, "R" NUMERIC, "RBI" NUMERIC,
    "SB" NUMERIC, "CS" NUMERIC, "SBN" NUMERIC, "BB" NUMERIC,
    "IBB" NUMERIC, "HBP" NUMERIC, "SF" NUMERIC, "SAC" NUMERIC,
    "SO" NUMERIC, "GDP" NUMERIC,
    "AVG" NUMERIC, "OBP" NUMERIC, "SLG" NUMERIC, "OPS" NUMERIC,
    "BABIP" NUMERIC, "ISO" NUMERIC, "wOBA" NUMERIC,
    exit_velo NUMERIC, adj_exit_velo NUMERIC, launch_angle NUMERIC,
    attack_angle NUMERIC, attack_dir NUMERIC, bat_speed NUMERIC,
    swing_length NUMERIC, swing_path_tilt NUMERIC, swing_miss_pct NUMERIC,
    swings INTEGER, takes INTEGER, whiffs INTEGER,
    barrel_rate NUMERIC, barrels_per_bbe_pct NUMERIC, barrels_per_pa_pct NUMERIC,
    barrels_total INTEGER, hard_hit_rate NUMERIC, hardhit_pct NUMERIC,
    batter_run_value_per_100 NUMERIC,
    "xAVG" NUMERIC, "xOBP" NUMERIC, "xSLG" NUMERIC, "xwOBA" NUMERIC,
    "xAVGdiff" NUMERIC, "xOBPdiff" NUMERIC, "xSLGdiff" NUMERIC,
    "BB_pct" NUMERIC, "K_pct" NUMERIC, "BBdist" INTEGER, "Kdist" INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season_id, stat_period)
);

CREATE INDEX idx_batting_stats_player ON player_stats_batting(player_id);
CREATE INDEX idx_batting_stats_season ON player_stats_batting(season_id);
CREATE INDEX idx_batting_stats_period ON player_stats_batting(stat_period);
