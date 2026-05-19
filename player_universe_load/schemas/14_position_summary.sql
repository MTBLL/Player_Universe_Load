-- Position Summary
-- Pool-level valuation aggregates per (position, valuation_type). Captures
-- the auction-pricing engine's choices: per-position budget pools, replacement
-- baselines, and dollars-per-z conversion rates for each scoring category.
-- Without this, the dollar_values in player_valuation_details are unexplained.
DROP TABLE IF EXISTS position_summary CASCADE;

CREATE TABLE position_summary (
    id SERIAL PRIMARY KEY,
    position VARCHAR(8) NOT NULL,
    role VARCHAR(10) NOT NULL,  -- HITTER | PITCHER
    valuation_type VARCHAR(20) NOT NULL,
    rostered_count INTEGER,
    replacement_tier_count INTEGER,
    total_budget NUMERIC,

    -- Hitter categories: R, HR, RBI, SBN, OBP, SLG.
    -- Column names quoted to preserve case (Postgres folds unquoted -> lower).
    "budget_R" NUMERIC, "budget_HR" NUMERIC, "budget_RBI" NUMERIC,
    "budget_SBN" NUMERIC, "budget_OBP" NUMERIC, "budget_SLG" NUMERIC,
    "pool_total_z_R" NUMERIC, "pool_total_z_HR" NUMERIC, "pool_total_z_RBI" NUMERIC,
    "pool_total_z_SBN" NUMERIC, "pool_total_z_OBP" NUMERIC, "pool_total_z_SLG" NUMERIC,
    "dollars_per_z_R" NUMERIC, "dollars_per_z_HR" NUMERIC, "dollars_per_z_RBI" NUMERIC,
    "dollars_per_z_SBN" NUMERIC, "dollars_per_z_OBP" NUMERIC, "dollars_per_z_SLG" NUMERIC,
    "replacement_baseline_R" NUMERIC, "replacement_baseline_HR" NUMERIC,
    "replacement_baseline_RBI" NUMERIC, "replacement_baseline_SBN" NUMERIC,
    "replacement_baseline_OBP" NUMERIC, "replacement_baseline_SLG" NUMERIC,

    -- Pitcher categories: IP, ERA, WHIP, K/9, QS, SVHD (RP-specific)
    "budget_IP" NUMERIC, "budget_ERA" NUMERIC, "budget_WHIP" NUMERIC,
    "budget_K/9" NUMERIC, "budget_QS" NUMERIC, "budget_SVHD" NUMERIC,
    "pool_total_z_IP" NUMERIC, "pool_total_z_ERA" NUMERIC, "pool_total_z_WHIP" NUMERIC,
    "pool_total_z_K/9" NUMERIC, "pool_total_z_QS" NUMERIC, "pool_total_z_SVHD" NUMERIC,
    "dollars_per_z_IP" NUMERIC, "dollars_per_z_ERA" NUMERIC, "dollars_per_z_WHIP" NUMERIC,
    "dollars_per_z_K/9" NUMERIC, "dollars_per_z_QS" NUMERIC, "dollars_per_z_SVHD" NUMERIC,
    "replacement_baseline_IP" NUMERIC, "replacement_baseline_ERA" NUMERIC,
    "replacement_baseline_WHIP" NUMERIC, "replacement_baseline_K/9" NUMERIC,
    "replacement_baseline_QS" NUMERIC, "replacement_baseline_SVHD" NUMERIC,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(position, valuation_type)
);

CREATE INDEX idx_position_summary_position ON position_summary(position);
CREATE INDEX idx_position_summary_valuation_type ON position_summary(valuation_type);
CREATE INDEX idx_position_summary_role ON position_summary(role);
