-- Derived views.
-- These run AFTER all base tables (sorted glob order: 16 > 01..15), so every
-- table they reference already exists in its freshly-recreated form. The base
-- tables are dropped with CASCADE on each load, which also drops any view built
-- on them; recreating the views here keeps them in lockstep with each reload.
-- CREATE OR REPLACE keeps the file idempotent when run outside the load flow.

-- Flattened per-position valuation rows.
-- player_valuations.by_position is a JSONB map (position -> {tier, total_z,
-- total_dollars, z_scores, dollar_values, shadow}). This view explodes that map
-- into one row per (valuation, position) so consumers can filter/order on
-- shadow / position / tier SQL-side instead of parsing JSONB client-side.
--
-- shadow = false -> real auction value (player is in this pool's roster/RLP/below
--                   tier list; tier reflects swap-pass-settled pricing).
-- shadow = true  -> display-only re-scoring (player NOT in this pool; stats
--                   re-scored against the pool's archetype). NOT a real auction
--                   price. Consumers must distinguish it visually.
CREATE OR REPLACE VIEW v_player_valuation_by_position AS
SELECT
    pv.player_id,
    pv.season_id,
    pv.valuation_type,
    bp.key                              AS position,
    (bp.value->>'tier')                 AS tier,
    (bp.value->>'total_z')::numeric     AS total_z,
    (bp.value->>'total_dollars')::numeric AS total_dollars,
    (bp.value->>'shadow')::boolean      AS shadow
FROM player_valuations pv
CROSS JOIN LATERAL jsonb_each(pv.by_position) AS bp(key, value)
WHERE pv.by_position IS NOT NULL;
