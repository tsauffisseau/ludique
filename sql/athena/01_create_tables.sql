-- Amazon Athena DDL over the Parquet lake exported by `python -m bgg_pipeline export --s3`.
-- Replace s3://YOUR_BUCKET/bgg with your bucket and BGG_S3_PREFIX before running.
-- Run statements one by one in the Athena console (Athena executes a single statement per query).

CREATE DATABASE IF NOT EXISTS bgg_lake;

-- Bronze: raw API responses, partitioned by ingestion date (Hive layout).
CREATE EXTERNAL TABLE IF NOT EXISTS bgg_lake.bronze_bgg_thing (
    run_id          string,
    batch_no        int,
    requested_ids   array<bigint>,
    source_url      string,
    http_status     smallint,
    fetched_at      timestamp,
    payload_sha256  string,
    payload         string
)
PARTITIONED BY (ingestion_date string)
STORED AS PARQUET
LOCATION 's3://YOUR_BUCKET/bgg/bronze/bgg_thing/';

MSCK REPAIR TABLE bgg_lake.bronze_bgg_thing;

-- Silver
CREATE EXTERNAL TABLE IF NOT EXISTS bgg_lake.silver_game_snapshots (
    game_id            bigint,
    snapshot_date      date,
    users_rated        bigint,
    average_rating     double,
    bayes_average      double,
    rating_stddev      double,
    bgg_rank           bigint,
    num_weights        bigint,
    weight_complexity  double,
    owned              bigint,
    trading            bigint,
    wanting            bigint,
    wishing            bigint,
    num_comments       bigint,
    source_fetched_at  timestamp
)
STORED AS PARQUET
LOCATION 's3://YOUR_BUCKET/bgg/silver/game_snapshots/';

CREATE EXTERNAL TABLE IF NOT EXISTS bgg_lake.silver_game_links (
    game_id    bigint,
    link_type  string,
    link_id    bigint,
    link_name  string
)
STORED AS PARQUET
LOCATION 's3://YOUR_BUCKET/bgg/silver/game_links/';

-- Gold (exported from PostgreSQL)
CREATE EXTERNAL TABLE IF NOT EXISTS bgg_lake.dim_game (
    game_id               int,
    game_name             string,
    min_players           int,
    max_players           int,
    best_with_min         int,
    best_with_max         int,
    playing_time          int,
    min_playtime          int,
    max_playtime          int,
    min_age               int,
    weight_bucket         string,
    playtime_bucket       string,
    player_count_profile  string,
    supports_solo         boolean,
    is_rating_reliable    boolean,
    is_released           boolean,
    n_mechanics           int,
    n_categories          int,
    n_designers           int,
    n_publishers          int,
    description           string,
    thumbnail_url         string,
    bgg_url               string,
    updated_at            timestamp
)
STORED AS PARQUET
LOCATION 's3://YOUR_BUCKET/bgg/gold/dim_game/';

CREATE EXTERNAL TABLE IF NOT EXISTS bgg_lake.dim_mechanic (
    mechanic_id     int,
    mechanic_name   string,
    is_placeholder  boolean,
    n_games         int
)
STORED AS PARQUET
LOCATION 's3://YOUR_BUCKET/bgg/gold/dim_mechanic/';

CREATE EXTERNAL TABLE IF NOT EXISTS bgg_lake.bridge_game_mechanic (
    game_id            int,
    mechanic_id        int,
    allocation_weight  double
)
STORED AS PARQUET
LOCATION 's3://YOUR_BUCKET/bgg/gold/bridge_game_mechanic/';

CREATE EXTERNAL TABLE IF NOT EXISTS bgg_lake.fact_game_snapshot (
    game_id            int,
    snapshot_date_key  int,
    year_published     int,
    average_rating     double,
    bayes_average      double,
    rating_stddev      double,
    users_rated        int,
    bgg_rank           int,
    weight_complexity  double,
    num_weights        int,
    owned              int,
    wishing            int,
    wanting            int,
    trading            int,
    num_comments       int,
    loaded_at          timestamp
)
STORED AS PARQUET
LOCATION 's3://YOUR_BUCKET/bgg/gold/fact_game_snapshot/';
