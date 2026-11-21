-- Q1 - How have supply, complexity and perceived quality evolved decade after decade?
--
-- Supply metrics (games released, solo share) use every game; quality metrics
-- (rating, weight) use only games with >= 30 ratings (is_rating_reliable).
DROP VIEW IF EXISTS mart_decade_trends CASCADE;
CREATE VIEW mart_decade_trends AS
WITH base AS (
    SELECT f.*, g.is_rating_reliable, g.supports_solo, g.playing_time, y.decade, y.decade_label
    FROM fact_game_latest AS f
    JOIN dim_game AS g ON g.game_id = f.game_id
    JOIN dim_year AS y ON y.year_published = f.year_published
    WHERE y.is_known
      AND y.year_published <= EXTRACT(YEAR FROM CURRENT_DATE)
)
SELECT
    decade_label,
    MIN(decade)                                                                   AS decade_sort,
    COUNT(*)                                                                      AS n_games_released,
    COUNT(*) FILTER (WHERE is_rating_reliable)                                    AS n_games_reliable,
    ROUND(AVG(average_rating)    FILTER (WHERE is_rating_reliable)::NUMERIC, 2)   AS avg_rating,
    ROUND(AVG(weight_complexity) FILTER (WHERE is_rating_reliable)::NUMERIC, 2)   AS avg_weight,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY playing_time)                     AS median_playing_time_min,
    ROUND(AVG(supports_solo::INT) * 100, 1)                                       AS pct_solo_capable,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY owned)                            AS median_owned,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)                            AS pct_of_catalogue
FROM base
GROUP BY decade_label
ORDER BY decade_sort;
