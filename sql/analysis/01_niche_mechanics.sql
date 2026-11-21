-- 01 · Niche mechanics: well rated, yet few games use them.
-- Business question: which mechanics deliver above-average ratings while still being rare
-- in the catalogue (i.e. a differentiation opportunity for a publisher)?
-- Technique: aggregation with FILTER, catalogue benchmark in a CTE, PERCENT_RANK window.
WITH catalogue AS (
    SELECT AVG(f.average_rating) AS avg_rating
    FROM fact_game_latest AS f
    JOIN dim_game AS g ON g.game_id = f.game_id
    WHERE g.is_rating_reliable
),
per_mechanic AS (
    SELECT
        m.mechanic_name,
        COUNT(*)                                                     AS n_games,
        COUNT(*) FILTER (WHERE g.is_rating_reliable)                 AS n_reliable,
        AVG(f.average_rating) FILTER (WHERE g.is_rating_reliable)    AS avg_rating
    FROM bridge_game_mechanic AS b
    JOIN dim_mechanic     AS m ON m.mechanic_id = b.mechanic_id
    JOIN fact_game_latest AS f ON f.game_id = b.game_id
    JOIN dim_game         AS g ON g.game_id = b.game_id
    GROUP BY m.mechanic_name
    HAVING COUNT(*) FILTER (WHERE g.is_rating_reliable) >= 10   -- minimum statistical support
)
SELECT
    p.mechanic_name,
    p.n_games,
    ROUND(p.avg_rating::NUMERIC, 2)                                   AS avg_rating,
    ROUND((p.avg_rating - c.avg_rating)::NUMERIC, 2)                  AS rating_lift,
    ROUND((100 * PERCENT_RANK() OVER (ORDER BY p.n_games))::NUMERIC)  AS supply_percentile
FROM per_mechanic AS p
CROSS JOIN catalogue AS c
WHERE p.avg_rating > c.avg_rating
ORDER BY supply_percentile, rating_lift DESC
LIMIT 10;
