-- Q3 - Do players reward complexity? Rating, engagement and reach by weight bucket,
--      overall and per market era (GROUPING SETS gives both levels in one pass).
--
-- corr_weight_rating is Pearson's r between weight and average rating within the era
-- (reliable games only): the headline "does heavier = better rated?" number.
DROP VIEW IF EXISTS mart_complexity_vs_rating CASCADE;
CREATE VIEW mart_complexity_vs_rating AS
WITH base AS (
    SELECT f.*, g.weight_bucket, g.playing_time, y.market_era
    FROM fact_game_latest AS f
    JOIN dim_game AS g ON g.game_id = f.game_id
    JOIN dim_year AS y ON y.year_published = f.year_published
    WHERE g.is_rating_reliable
      AND f.weight_complexity IS NOT NULL
),
correlations AS (
    SELECT market_era, CORR(weight_complexity, average_rating) AS r FROM base GROUP BY market_era
    UNION ALL
    SELECT 'All eras', CORR(weight_complexity, average_rating) FROM base
),
buckets AS (
    SELECT
        COALESCE(market_era, 'All eras')                            AS market_era,
        weight_bucket,
        COUNT(*)                                                    AS n_games,
        ROUND(AVG(average_rating)::NUMERIC, 2)                      AS avg_rating,
        ROUND(AVG(bayes_average)::NUMERIC, 2)                       AS avg_bayes_average,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY users_rated)    AS median_users_rated,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY owned)          AS median_owned,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY playing_time)   AS median_playing_time_min
    FROM base
    GROUP BY GROUPING SETS ((market_era, weight_bucket), (weight_bucket))
)
SELECT b.*, ROUND(c.r::NUMERIC, 3) AS corr_weight_rating
FROM buckets AS b
JOIN correlations AS c ON c.market_era = b.market_era
ORDER BY b.market_era, b.weight_bucket;
