-- Roster Slots Table
DROP TABLE IF EXISTS roster_slots CASCADE;

CREATE TABLE roster_slots (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL REFERENCES players(id_espn) ON DELETE CASCADE,
    lineup_slot VARCHAR(20) NOT NULL,
    acquisition_type VARCHAR(20),
    acquisition_date TIMESTAMP,
    keeper_value INTEGER,
    -- Position name -> ISO date the player became eligible at that position.
    -- Variable-key map (positions differ per player), so JSONB rather than
    -- columns. Flattened from the trx RosterSlotPlayer.eligible_date_by_position.
    eligible_date_by_position JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, player_id, season_id)
);

CREATE INDEX idx_roster_team ON roster_slots(team_id);
CREATE INDEX idx_roster_player ON roster_slots(player_id);
CREATE INDEX idx_roster_slot ON roster_slots(lineup_slot);
CREATE INDEX idx_roster_league ON roster_slots(league_id);
