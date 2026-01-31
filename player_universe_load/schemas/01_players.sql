-- Players Table
DROP TABLE IF EXISTS players CASCADE;

CREATE TABLE players (
    id_espn INTEGER PRIMARY KEY,
    id_fangraphs VARCHAR(20),
    id_xmlbam INTEGER,
    name VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    name_ascii VARCHAR(255),
    slug VARCHAR(255),
    fangraphs_api_route VARCHAR(500),
    headshot VARCHAR(500),
    primary_position VARCHAR(10),
    eligible_slots JSONB,
    pro_team VARCHAR(10),
    weight NUMERIC(5,1),
    display_weight VARCHAR(20),
    height INTEGER,
    display_height VARCHAR(10),
    bats VARCHAR(10),
    throws VARCHAR(10),
    date_of_birth DATE,
    birth_place JSONB,
    debut_year INTEGER,
    injury_status VARCHAR(20),
    status VARCHAR(20),
    injured BOOLEAN,
    active BOOLEAN,
    jersey INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_players_pro_team ON players(pro_team);
CREATE INDEX idx_players_primary_position ON players(primary_position);
CREATE INDEX idx_players_active ON players(active);
CREATE INDEX idx_players_name ON players(name);
CREATE INDEX idx_players_fangraphs ON players(id_fangraphs);
CREATE INDEX idx_players_slug ON players(slug);
CREATE UNIQUE INDEX idx_players_xmlbam ON players(id_xmlbam) WHERE id_xmlbam IS NOT NULL;
