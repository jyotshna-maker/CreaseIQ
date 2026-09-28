-- Generated from src/creaseiq/db/models.py by `creaseiq report`. Do not edit.

CREATE TABLE franchise (
	franchise_id VARCHAR(32) NOT NULL, 
	canonical_name VARCHAR(80) NOT NULL, 
	short_code VARCHAR(8) NOT NULL, 
	active BOOLEAN NOT NULL, 
	lineage_note TEXT, 
	PRIMARY KEY (franchise_id), 
	UNIQUE (canonical_name)
);

CREATE TABLE model_run (
	run_id VARCHAR(40) NOT NULL, 
	created_at DATETIME NOT NULL, 
	model_name VARCHAR(60) NOT NULL, 
	tier VARCHAR(10) NOT NULL, 
	params_json TEXT NOT NULL, 
	data_sha256 VARCHAR(64) NOT NULL, 
	git_commit VARCHAR(40) NOT NULL, 
	metrics_json TEXT NOT NULL, 
	artifact_path TEXT NOT NULL, 
	artifact_sha256 VARCHAR(64) NOT NULL, 
	PRIMARY KEY (run_id)
);

CREATE TABLE official (
	official_id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	PRIMARY KEY (official_id), 
	UNIQUE (name)
);

CREATE TABLE player (
	player_id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	PRIMARY KEY (player_id), 
	UNIQUE (name)
);

CREATE TABLE venue (
	venue_id VARCHAR(32) NOT NULL, 
	canonical_name VARCHAR(120) NOT NULL, 
	city VARCHAR(60) NOT NULL, 
	country VARCHAR(40) NOT NULL, 
	PRIMARY KEY (venue_id), 
	UNIQUE (canonical_name)
);

CREATE TABLE prediction_log (
	prediction_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	run_id VARCHAR(40), 
	tier VARCHAR(10) NOT NULL, 
	team_a_id VARCHAR(32) NOT NULL, 
	team_b_id VARCHAR(32) NOT NULL, 
	venue_id VARCHAR(32) NOT NULL, 
	stage VARCHAR(16) NOT NULL, 
	toss_json TEXT, 
	p_a FLOAT NOT NULL, 
	latency_ms FLOAT NOT NULL, 
	PRIMARY KEY (prediction_id), 
	CONSTRAINT ck_probability CHECK (p_a >= 0 AND p_a <= 1), 
	FOREIGN KEY(team_a_id) REFERENCES franchise (franchise_id), 
	FOREIGN KEY(team_b_id) REFERENCES franchise (franchise_id), 
	FOREIGN KEY(venue_id) REFERENCES venue (venue_id)
);

CREATE TABLE season (
	season_id INTEGER NOT NULL, 
	season_year INTEGER NOT NULL, 
	raw_label VARCHAR(10) NOT NULL, 
	host_note TEXT, 
	n_matches INTEGER NOT NULL, 
	champion_id VARCHAR(32), 
	PRIMARY KEY (season_id), 
	UNIQUE (season_year), 
	FOREIGN KEY(champion_id) REFERENCES franchise (franchise_id)
);

CREATE TABLE team_alias (
	alias VARCHAR(80) NOT NULL, 
	franchise_id VARCHAR(32) NOT NULL, 
	valid_from_year INTEGER NOT NULL, 
	valid_to_year INTEGER NOT NULL, 
	PRIMARY KEY (alias), 
	CONSTRAINT ck_alias_window CHECK (valid_from_year <= valid_to_year), 
	FOREIGN KEY(franchise_id) REFERENCES franchise (franchise_id)
);

CREATE TABLE "match" (
	match_id INTEGER NOT NULL, 
	season_id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	match_number INTEGER, 
	stage VARCHAR(16) NOT NULL, 
	venue_id VARCHAR(32) NOT NULL, 
	team1_id VARCHAR(32) NOT NULL, 
	team2_id VARCHAR(32) NOT NULL, 
	toss_winner_id VARCHAR(32) NOT NULL, 
	toss_decision VARCHAR(5) NOT NULL, 
	bat_first_id VARCHAR(32) NOT NULL, 
	team1_runs INTEGER NOT NULL, 
	team1_wkts INTEGER NOT NULL, 
	team2_runs INTEGER NOT NULL, 
	team2_wkts INTEGER NOT NULL, 
	first_innings_runs FLOAT, 
	second_innings_runs FLOAT, 
	winner_id VARCHAR(32), 
	super_over_winner_id VARCHAR(32), 
	result_type VARCHAR(10) NOT NULL, 
	margin_type VARCHAR(8), 
	margin_value FLOAT, 
	dls_flag BOOLEAN NOT NULL, 
	voided BOOLEAN NOT NULL, 
	team1_home BOOLEAN NOT NULL, 
	team2_home BOOLEAN NOT NULL, 
	potm_player_id INTEGER, 
	referee_id INTEGER, 
	umpire1_id INTEGER, 
	umpire2_id INTEGER, 
	tv_umpire_id INTEGER, 
	reserve_umpire_id INTEGER, 
	PRIMARY KEY (match_id), 
	CONSTRAINT uq_match_natural_key UNIQUE (date, team1_id, team2_id), 
	CONSTRAINT ck_toss_decision CHECK (toss_decision IN ('bat', 'field')), 
	CONSTRAINT ck_result_type CHECK (result_type IN ('complete', 'tie', 'no result')), 
	CONSTRAINT ck_distinct_teams CHECK (team1_id <> team2_id), 
	CONSTRAINT ck_winner_iff_complete CHECK ((result_type = 'complete') = (winner_id IS NOT NULL)), 
	FOREIGN KEY(season_id) REFERENCES season (season_id), 
	FOREIGN KEY(venue_id) REFERENCES venue (venue_id), 
	FOREIGN KEY(team1_id) REFERENCES franchise (franchise_id), 
	FOREIGN KEY(team2_id) REFERENCES franchise (franchise_id), 
	FOREIGN KEY(toss_winner_id) REFERENCES franchise (franchise_id), 
	FOREIGN KEY(bat_first_id) REFERENCES franchise (franchise_id), 
	FOREIGN KEY(winner_id) REFERENCES franchise (franchise_id), 
	FOREIGN KEY(super_over_winner_id) REFERENCES franchise (franchise_id), 
	FOREIGN KEY(potm_player_id) REFERENCES player (player_id), 
	FOREIGN KEY(referee_id) REFERENCES official (official_id), 
	FOREIGN KEY(umpire1_id) REFERENCES official (official_id), 
	FOREIGN KEY(umpire2_id) REFERENCES official (official_id), 
	FOREIGN KEY(tv_umpire_id) REFERENCES official (official_id), 
	FOREIGN KEY(reserve_umpire_id) REFERENCES official (official_id)
);

CREATE INDEX ix_match_date ON "match" (date);

CREATE INDEX ix_match_season ON "match" (season_id);

CREATE INDEX ix_match_venue ON "match" (venue_id);

CREATE TABLE match_player (
	match_id INTEGER NOT NULL, 
	team_id VARCHAR(32) NOT NULL, 
	player_id INTEGER NOT NULL, 
	slot_no INTEGER NOT NULL, 
	PRIMARY KEY (match_id, team_id, player_id), 
	FOREIGN KEY(match_id) REFERENCES "match" (match_id), 
	FOREIGN KEY(team_id) REFERENCES franchise (franchise_id), 
	FOREIGN KEY(player_id) REFERENCES player (player_id)
);

CREATE INDEX ix_match_player_player ON match_player (player_id);

CREATE VIEW v_team_season_summary AS SELECT s.season_year, f.franchise_id, f.canonical_name, COUNT(*) AS matches, SUM(CASE WHEN m.winner_id = f.franchise_id THEN 1 ELSE 0 END) AS wins, SUM(CASE WHEN m.result_type = 'complete' AND m.winner_id <> f.franchise_id THEN 1 ELSE 0 END) AS losses, SUM(CASE WHEN m.result_type <> 'complete' THEN 1 ELSE 0 END) AS no_decision FROM match m JOIN season s ON s.season_id = m.season_id JOIN franchise f ON f.franchise_id IN (m.team1_id, m.team2_id) GROUP BY s.season_year, f.franchise_id, f.canonical_name;

CREATE VIEW v_head_to_head AS SELECT a.franchise_id AS team_id, b.franchise_id AS opponent_id, COUNT(*) AS meetings, SUM(CASE WHEN m.winner_id = a.franchise_id THEN 1 ELSE 0 END) AS wins, SUM(CASE WHEN m.winner_id = b.franchise_id THEN 1 ELSE 0 END) AS losses FROM match m JOIN franchise a ON a.franchise_id IN (m.team1_id, m.team2_id) JOIN franchise b ON b.franchise_id IN (m.team1_id, m.team2_id) AND b.franchise_id <> a.franchise_id GROUP BY a.franchise_id, b.franchise_id;
