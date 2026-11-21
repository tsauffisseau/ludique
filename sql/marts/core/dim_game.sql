-- Dimension: one row per board game (grain = BGG game id). Descriptive attributes only;
-- time-varying measures live in fact_game_snapshot. Slowly changing dimension type 1:
-- new games are inserted, existing ones are overwritten with their latest attributes.
-- The publication year is reached through fact_game_snapshot.year_published -> dim_year,
-- a single source of truth (with an "unknown" member) for time analysis.
CREATE TABLE IF NOT EXISTS dim_game (
    game_id               INTEGER  PRIMARY KEY,
    game_name             TEXT     NOT NULL,
    min_players           SMALLINT,
    max_players           SMALLINT,
    best_with_min         SMALLINT,
    best_with_max         SMALLINT,
    playing_time          INTEGER,
    min_playtime          INTEGER,
    max_playtime          INTEGER,
    min_age               SMALLINT,
    weight_bucket         TEXT     NOT NULL,
    playtime_bucket       TEXT     NOT NULL,
    player_count_profile  TEXT     NOT NULL,
    supports_solo         BOOLEAN,
    is_rating_reliable    BOOLEAN  NOT NULL,
    is_released           BOOLEAN  NOT NULL,
    n_mechanics           SMALLINT NOT NULL,
    n_categories          SMALLINT NOT NULL,
    n_designers           SMALLINT NOT NULL,
    n_publishers          SMALLINT NOT NULL,
    description           TEXT,
    thumbnail_url         TEXT,
    bgg_url               TEXT     NOT NULL,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO dim_game AS d (
    game_id, game_name, min_players, max_players, best_with_min, best_with_max,
    playing_time, min_playtime, max_playtime, min_age,
    weight_bucket, playtime_bucket, player_count_profile, supports_solo,
    is_rating_reliable, is_released, n_mechanics, n_categories, n_designers, n_publishers,
    description, thumbnail_url, bgg_url
)
SELECT
    g.game_id, g.game_name, g.min_players, g.max_players, g.best_with_min, g.best_with_max,
    g.playing_time, g.min_playtime, g.max_playtime, g.min_age,
    g.weight_bucket, g.playtime_bucket, g.player_count_profile, g.supports_solo,
    g.is_rating_reliable, g.is_released,
    COUNT(l.link_id) FILTER (WHERE l.link_type = 'mechanic'),
    COUNT(l.link_id) FILTER (WHERE l.link_type = 'category'),
    COUNT(l.link_id) FILTER (WHERE l.link_type = 'designer'),
    COUNT(l.link_id) FILTER (WHERE l.link_type = 'publisher'),
    g.description, g.thumbnail_url,
    'https://boardgamegeek.com/boardgame/' || g.game_id
FROM int_games AS g
LEFT JOIN int_game_links AS l ON l.game_id = g.game_id
GROUP BY
    g.game_id, g.game_name, g.min_players, g.max_players, g.best_with_min, g.best_with_max,
    g.playing_time, g.min_playtime, g.max_playtime, g.min_age,
    g.weight_bucket, g.playtime_bucket, g.player_count_profile, g.supports_solo,
    g.is_rating_reliable, g.is_released, g.description, g.thumbnail_url
ON CONFLICT (game_id) DO UPDATE SET
    game_name            = EXCLUDED.game_name,
    min_players          = EXCLUDED.min_players,
    max_players          = EXCLUDED.max_players,
    best_with_min        = EXCLUDED.best_with_min,
    best_with_max        = EXCLUDED.best_with_max,
    playing_time         = EXCLUDED.playing_time,
    min_playtime         = EXCLUDED.min_playtime,
    max_playtime         = EXCLUDED.max_playtime,
    min_age              = EXCLUDED.min_age,
    weight_bucket        = EXCLUDED.weight_bucket,
    playtime_bucket      = EXCLUDED.playtime_bucket,
    player_count_profile = EXCLUDED.player_count_profile,
    supports_solo        = EXCLUDED.supports_solo,
    is_rating_reliable   = EXCLUDED.is_rating_reliable,
    is_released          = EXCLUDED.is_released,
    n_mechanics          = EXCLUDED.n_mechanics,
    n_categories         = EXCLUDED.n_categories,
    n_designers          = EXCLUDED.n_designers,
    n_publishers         = EXCLUDED.n_publishers,
    description          = EXCLUDED.description,
    thumbnail_url        = EXCLUDED.thumbnail_url,
    updated_at           = NOW();
