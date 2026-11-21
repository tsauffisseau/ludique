-- Silver landing tables in PostgreSQL, (re)loaded from data/silver/*.parquet with COPY.
-- Silver is a full, replayable image of the Bronze zone, so it is truncated and reloaded
-- on every run. Incrementality lives in the Gold layer (dimensions upserted, snapshot
-- fact appended), which is where history is kept.
CREATE SCHEMA IF NOT EXISTS silver;

DROP TABLE IF EXISTS silver.games CASCADE;
CREATE TABLE silver.games (
    game_id            INTEGER PRIMARY KEY,
    game_name          TEXT NOT NULL,
    year_published     INTEGER,
    min_players        INTEGER,
    max_players        INTEGER,
    best_with_min      INTEGER,
    best_with_max      INTEGER,
    playing_time       INTEGER,
    min_playtime       INTEGER,
    max_playtime       INTEGER,
    min_age            INTEGER,
    users_rated        INTEGER NOT NULL,
    average_rating     DOUBLE PRECISION,
    bayes_average      DOUBLE PRECISION,
    rating_stddev      DOUBLE PRECISION,
    bgg_rank           INTEGER,
    num_weights        INTEGER NOT NULL,
    weight_complexity  DOUBLE PRECISION,
    owned              INTEGER NOT NULL,
    trading            INTEGER NOT NULL,
    wanting            INTEGER NOT NULL,
    wishing            INTEGER NOT NULL,
    num_comments       INTEGER NOT NULL,
    description        TEXT,
    thumbnail_url      TEXT,
    image_url          TEXT,
    source_run_id      TEXT NOT NULL,
    source_fetched_at  TIMESTAMPTZ NOT NULL
);

DROP TABLE IF EXISTS silver.game_snapshots CASCADE;
CREATE TABLE silver.game_snapshots (
    game_id            INTEGER NOT NULL,
    snapshot_date      DATE NOT NULL,
    users_rated        INTEGER NOT NULL,
    average_rating     DOUBLE PRECISION,
    bayes_average      DOUBLE PRECISION,
    rating_stddev      DOUBLE PRECISION,
    bgg_rank           INTEGER,
    num_weights        INTEGER NOT NULL,
    weight_complexity  DOUBLE PRECISION,
    owned              INTEGER NOT NULL,
    trading            INTEGER NOT NULL,
    wanting            INTEGER NOT NULL,
    wishing            INTEGER NOT NULL,
    num_comments       INTEGER NOT NULL,
    source_fetched_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (game_id, snapshot_date)
);

DROP TABLE IF EXISTS silver.game_links CASCADE;
CREATE TABLE silver.game_links (
    game_id    INTEGER NOT NULL,
    link_type  TEXT NOT NULL,
    link_id    INTEGER NOT NULL,
    link_name  TEXT NOT NULL,
    PRIMARY KEY (game_id, link_type, link_id)
);
