-- Staging: dated metric snapshots (one row per game per snapshot date).
DROP VIEW IF EXISTS stg_game_snapshots CASCADE;
CREATE VIEW stg_game_snapshots AS
SELECT
    game_id, snapshot_date,
    users_rated, average_rating, bayes_average, rating_stddev, bgg_rank,
    num_weights, weight_complexity,
    owned, trading, wanting, wishing, num_comments,
    source_fetched_at
FROM silver.game_snapshots;
