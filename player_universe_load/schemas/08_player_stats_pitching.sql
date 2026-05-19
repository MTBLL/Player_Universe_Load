-- Player Stats - Pitching
DROP TABLE IF EXISTS player_stats_pitching CASCADE;

CREATE TABLE player_stats_pitching (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    stat_period VARCHAR(50) DEFAULT 'current_season',
    "GP" NUMERIC, "GS" NUMERIC, "OUTS" NUMERIC, "IP" NUMERIC,
    "TBF" NUMERIC, "H" NUMERIC, "R" NUMERIC, "ER" NUMERIC,
    "HR" NUMERIC, "BB" NUMERIC, "IBB" NUMERIC, "K" NUMERIC,
    "HBP" NUMERIC, "WP" NUMERIC, "BK" NUMERIC,
    "W" NUMERIC, "L" NUMERIC, "WPCT" NUMERIC, "QS" NUMERIC,
    "SV" NUMERIC, "HLD" NUMERIC, "SVHD" NUMERIC, "SVO" NUMERIC,
    "BLSV" NUMERIC, "SV_pct" NUMERIC,
    "ERA" NUMERIC, "WHIP" NUMERIC, "OBA" NUMERIC, "OOBP" NUMERIC,
    k_bb_ratio NUMERIC, k_per_9 NUMERIC, bb_per_9 NUMERIC,
    velo NUMERIC, spin_rate NUMERIC, eff_min_vel NUMERIC,
    percieved_velo NUMERIC, release_extension NUMERIC,
    release_pos_x NUMERIC, release_pos_z NUMERIC,
    break_z NUMERIC, induced_break_z NUMERIC,
    break_x_arm_side NUMERIC, break_x_batter_in NUMERIC, arm_angle NUMERIC,
    pitcher_run_exp NUMERIC, pitcher_run_value_per_100 NUMERIC,
    exit_velo NUMERIC, adj_exit_velo NUMERIC, launch_angle NUMERIC,
    swing_miss_pct NUMERIC, swings INTEGER, takes INTEGER, whiffs INTEGER,
    "xAVG" NUMERIC, "xOBP" NUMERIC, "xSLG" NUMERIC, "xwOBA" NUMERIC,
    "xAVGdiff" NUMERIC, "xOBPdiff" NUMERIC, "xSLGdiff" NUMERIC,
    -- Savant-against fields: rates the pitcher allowed batters
    "AVG" NUMERIC, "OBP" NUMERIC, "SLG" NUMERIC,
    "BABIP" NUMERIC, "ISO" NUMERIC,
    "BB_pct" NUMERIC, "K_pct" NUMERIC, "BBdist" NUMERIC,
    "BIP" NUMERIC, "PA" NUMERIC,
    pitches NUMERIC, total_pitches NUMERIC, pitch_percent NUMERIC,
    barrels_per_bbe_pct NUMERIC, barrels_per_bbe_pct_pct_rnk NUMERIC,
    barrels_per_pa_pct NUMERIC, barrels_per_pa_pct_pct_rnk NUMERIC,
    barrels_total NUMERIC, barrels_total_pct_rnk NUMERIC,
    hardhit_pct NUMERIC, hardhit_pct_pct_rnk NUMERIC,
    rate_ideal_attack_angle NUMERIC, run_exp NUMERIC,
    "wOBA" NUMERIC, "wOBAdiff" NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season_id, stat_period)
);

CREATE INDEX idx_pitching_stats_player ON player_stats_pitching(player_id);
CREATE INDEX idx_pitching_stats_season ON player_stats_pitching(season_id);
CREATE INDEX idx_pitching_stats_period ON player_stats_pitching(stat_period);
