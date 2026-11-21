-- Staging: 1:1 view over the Silver landing table. Renaming/selection only, no business logic.
DROP VIEW IF EXISTS stg_games CASCADE;
CREATE VIEW stg_games AS
SELECT
    game_id, game_name, year_published,
    min_players, max_players, best_with_min, best_with_max,
    playing_time, min_playtime, max_playtime, min_age,
    users_rated, average_rating, bayes_average, rating_stddev, bgg_rank,
    num_weights, weight_complexity,
    owned, trading, wanting, wishing, num_comments,
    description, thumbnail_url, source_fetched_at
FROM silver.games;
