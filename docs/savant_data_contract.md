# Savant Data Contract (Hasura ingestion)

Contract for the two Baseball Savant tables introduced when savant data was
split out of `player_projections`: **`player_pitch_arsenal`** (typed) and
**`player_savant`** (JSONB blobs). Source for both is `stats.savant.*` in the
loader input (`hitters.json` / `pitchers.json`).

> **Why two tables:** `pitch_arsenal` is a *list* (one row per pitch type) with
> a stable, batter/pitcher-identical schema → fully typed. The other five
> metrics are one-row-per-player dicts with wide, season-variable keys → JSONB,
> which absorbs Savant field drift without schema churn. `player_projections`
> is now **fangraphs-only** (genuine projections).

All observed (measured) data — **not** projections.

---

## Relationships to track in Hasura

Both tables FK `player_id → players(id_espn)`. Hasura auto-suggests:

| Relationship | Type | On |
|---|---|---|
| `players.player_pitch_arsenal` | array | `players.id_espn → player_pitch_arsenal.player_id` |
| `players.player_savant` | array | `players.id_espn → player_savant.player_id` |
| `player_pitch_arsenal.player` | object | reverse |
| `player_savant.player` | object | reverse |

After a `sync-to-neon`, reload Hasura metadata, then **Track** both tables and
accept the suggested relationships.

---

## Table: `player_pitch_arsenal`

One typed row per **(player_id, season_id, player_type, pitch_type)**.
`player_type` = `pitcher` (pitches thrown) or `hitter` (pitches faced) — same
schema for both. `UNIQUE(player_id, season_id, player_type, pitch_type)`.

| Column | Type | Notes |
|---|---|---|
| `id` | int (PK) | serial |
| `player_id` | int (FK) | → players.id_espn |
| `season_id` | int | |
| `player_type` | text | `pitcher` \| `hitter` |
| `pitch_type` | text | code, e.g. `FF`, `SL`, `CH`, `ST`, `SI`, `FS` |
| `pitch_name` | text | e.g. `4-Seam Fastball` |
| `pitches` | int | count |
| `pitch_usage_pct` | numeric | |
| `PA` | int | |
| `AVG`, `SLG`, `wOBA` | numeric | against this pitch |
| `xAVG`, `xSLG`, `xwOBA` | numeric | expected; `xAVG`/`xSLG` nullable |
| `K_pct`, `whiff_pct`, `put_away_pct`, `hardhit_pct` | numeric | `hardhit_pct` nullable |
| `run_value` | int | |
| `run_value_per_100` | numeric | per 100 pitches |
| `*_pct_rnk` (16 cols) | numeric | Savant percentile rank (0–100) for each metric above |
| `created_at`, `updated_at` | timestamp | |

GraphQL is fully typed — filter/sort/aggregate without JSON parsing:

```graphql
query NastiestPitches {
  player_pitch_arsenal(
    where: { player_type: { _eq: "pitcher" }, pitches: { _gte: 100 } }
    order_by: { whiff_pct: desc }
    limit: 10
  ) {
    pitch_name
    whiff_pct
    run_value_per_100
    player { name pro_team }
  }
}
```

---

## Table: `player_savant`

One row per **(player_id, season_id, metric, player_type)**; payload in JSONB
`data`. `UNIQUE(player_id, season_id, metric, player_type)`.

| Column | Type | Notes |
|---|---|---|
| `id` | int (PK) | serial |
| `player_id` | int (FK) | → players.id_espn |
| `season_id` | int | |
| `metric` | text | discriminator (see below) |
| `player_type` | text | `pitcher` \| `hitter` |
| `data` | jsonb | metric payload |
| `created_at`, `updated_at` | timestamp | |

`metric` populations:

| metric | population | `data` keys |
|---|---|---|
| `statcast` | both | 32 — `bbe, avg_launch_angle, sweetspot_pct, max_ev, avg_ev, ev50, fbld_ev, gb_ev, max_distance, avg_distance, avg_hr_distance, ev95_plus, ev95_pct, barrels, barrels_per_bbe_pct, barrels_per_pa_pct` + matching `*_pct_rnk` |
| `home_runs` | both | 18 — `year, hr_type, HR, xHR, xHRdiff, avg_hr_trot, doubters, mostly_gone, no_doubters, no_doubter_pct` + `*_pct_rnk` |
| `swing_take` | both | 16 — `year, team_id, PA, pitches, runs_all, runs_heart, runs_shadow, runs_chase, runs_waste` + `*_pct_rnk` |
| `sprint_speed` | **hitter-only** | 11 — `age, position, sprint_speed, hp_to_1b, bolts, competitive_runs, team_id` + `*_pct_rnk` |
| `expected_statistics` | **pitcher-only** | 29 — `year, PA, BIP, AVG, xAVG, xAVGdiff, SLG, xSLG, xSLGdiff, wOBA, xwOBA, wOBAdiff, ERA, xERA, xERAdiff` + `*_pct_rnk` |

`data` is heterogeneous JSON — Hasura exposes it as `jsonb`. Query a metric and
read fields client-side, or use Postgres `->>` in a view if you need typed
columns for a specific metric:

```graphql
query Barrels {
  player_savant(
    where: { metric: { _eq: "statcast" }, player_type: { _eq: "hitter" } }
  ) {
    player { name }
    data   # { barrels_per_pa_pct, avg_ev, max_ev, ... }
  }
}
```

> **Parquet / R2 note:** in the parquet artifacts the `data` column is a JSON
> **string** (not a struct) — `JSON.parse` it on the consumer. All NUMERIC
> columns in `player_pitch_arsenal` are emitted as `float64` (browser/WASM
> parquet readers can't decode `decimal128`). See `exporters/parquet.py`.

---

## Discoverability note

If you're looking for `pitch_arsenal` and can't find it: it is **no longer**
in `player_projections`. It is the typed `player_pitch_arsenal` table. The
other savant metrics are rows in `player_savant` keyed by `metric`.
`player_projections` now contains only fangraphs projections
(`preseason` / `updated` / `ros`).
