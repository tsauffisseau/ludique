-- Fact: periodic snapshot of each game's community metrics.
-- Grain = one row per game per snapshot date (weekly refresh), so ratings, rank and
-- owners can be followed over time.
--
-- Incremental load (high-watermark): only snapshots dated on or after the latest date
-- already loaded are processed (the last loaded day is re-checked to absorb a same-day
-- re-run), and ON CONFLICT ... WHERE IS DISTINCT FROM makes re-runs idempotent.
-- Older history is never reloaded. `python -m bgg_pipeline build --full-refresh` rebuilds it.
--
-- Measures: ratings/rank/weight are non-additive (average them); counts are additive
-- across games but semi-additive over time (never sum owned copies across dates).
-- BGG exposes no sales: `owned` (copies in collections) is the market-penetration proxy,
-- `wishing` (wishlists) the unmet-demand proxy.
CREATE TABLE IF NOT EXISTS fact_game_snapshot (
    game_id            INTEGER NOT NULL REFERENCES dim_game (game_id),
    snapshot_date_key  INTEGER NOT NULL REFERENCES dim_date (date_key),
    year_published     INTEGER NOT NULL REFERENCES dim_year (year_published),
    average_rating     DOUBLE PRECISION CHECK (average_rating BETWEEN 1 AND 10),
    bayes_average      DOUBLE PRECISION CHECK (bayes_average BETWEEN 1 AND 10),
    rating_stddev      DOUBLE PRECISION,
    users_rated        INTEGER NOT NULL CHECK (users_rated >= 0),
    bgg_rank           INTEGER,
    weight_complexity  DOUBLE PRECISION CHECK (weight_complexity BETWEEN 1 AND 5),
    num_weights        INTEGER NOT NULL,
    owned              INTEGER NOT NULL CHECK (owned >= 0),
    wishing            INTEGER NOT NULL CHECK (wishing >= 0),
    wanting            INTEGER NOT NULL,
    trading            INTEGER NOT NULL,
    num_comments       INTEGER NOT NULL,
    loaded_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, snapshot_date_key)
);

INSERT INTO fact_game_snapshot AS f (
    game_id, snapshot_date_key, year_published,
    average_rating, bayes_average, rating_stddev, users_rated, bgg_rank,
    weight_complexity, num_weights, owned, wishing, wanting, trading, num_comments
)
SELECT
    s.game_id,
    s.snapshot_date_key,
    COALESCE(g.year_published, 0),
    s.average_rating, s.bayes_average, s.rating_stddev, s.users_rated, s.bgg_rank,
    s.weight_complexity, s.num_weights, s.owned, s.wishing, s.wanting, s.trading, s.num_comments
FROM int_game_snapshots AS s
JOIN int_games AS g ON g.game_id = s.game_id
WHERE s.snapshot_date >= COALESCE(
    (SELECT MAX(d.date_actual)
     FROM fact_game_snapshot AS x
     JOIN dim_date AS d ON d.date_key = x.snapshot_date_key),
    DATE '1900-01-01'
)
ON CONFLICT (game_id, snapshot_date_key) DO UPDATE SET
    year_published    = EXCLUDED.year_published,
    average_rating    = EXCLUDED.average_rating,
    bayes_average     = EXCLUDED.bayes_average,
    rating_stddev     = EXCLUDED.rating_stddev,
    users_rated       = EXCLUDED.users_rated,
    bgg_rank          = EXCLUDED.bgg_rank,
    weight_complexity = EXCLUDED.weight_complexity,
    num_weights       = EXCLUDED.num_weights,
    owned             = EXCLUDED.owned,
    wishing           = EXCLUDED.wishing,
    wanting           = EXCLUDED.wanting,
    trading           = EXCLUDED.trading,
    num_comments      = EXCLUDED.num_comments,
    loaded_at         = NOW()
-- No-op updates are skipped: a re-processed row is only rewritten if a value changed,
-- so loaded_at stays a truthful audit trail.
WHERE (f.year_published, f.average_rating, f.bayes_average, f.rating_stddev, f.users_rated,
       f.bgg_rank, f.weight_complexity, f.num_weights, f.owned, f.wishing, f.wanting,
       f.trading, f.num_comments)
      IS DISTINCT FROM
      (EXCLUDED.year_published, EXCLUDED.average_rating, EXCLUDED.bayes_average,
       EXCLUDED.rating_stddev, EXCLUDED.users_rated, EXCLUDED.bgg_rank,
       EXCLUDED.weight_complexity, EXCLUDED.num_weights, EXCLUDED.owned, EXCLUDED.wishing,
       EXCLUDED.wanting, EXCLUDED.trading, EXCLUDED.num_comments);
