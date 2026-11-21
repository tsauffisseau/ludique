-- Q2 - Which mechanics are associated with the best ratings and the widest market
--      penetration, and which ones are gaining momentum in recent releases?
--
-- * rating_lift      : avg rating of the mechanic minus the catalogue average (reliable games).
-- * owned_share_pct  : share of all owned copies, allocated through the bridge weight
--                      (sums to 100 % across mechanics - no double counting).
-- * momentum_index   : share of 2015+ releases using the mechanic / same share for
--                      2000-2014 releases. > 1 = growing adoption by publishers.
--                      NULL when the mechanic has < 5 games in 2000-2014: a ratio over
--                      a near-zero base is noise ("x25 growth" from 1 game to 25).
DROP VIEW IF EXISTS mart_top_mechanics_trends CASCADE;
CREATE VIEW mart_top_mechanics_trends AS
WITH games AS (
    SELECT f.*, g.is_rating_reliable,
           f.year_published BETWEEN 2015 AND EXTRACT(YEAR FROM CURRENT_DATE) AS is_recent,
           f.year_published BETWEEN 2000 AND 2014                            AS is_prior
    FROM fact_game_latest AS f
    JOIN dim_game AS g ON g.game_id = f.game_id
),
catalogue AS (
    SELECT
        AVG(average_rating) FILTER (WHERE is_rating_reliable) AS avg_rating,
        SUM(owned)::NUMERIC                                    AS total_owned,
        COUNT(*) FILTER (WHERE is_recent)::NUMERIC             AS n_recent,
        COUNT(*) FILTER (WHERE is_prior)::NUMERIC              AS n_prior
    FROM games
),
per_mechanic AS (
    SELECT
        b.mechanic_id,
        COUNT(*)                                                        AS n_games,
        COUNT(*) FILTER (WHERE gm.is_rating_reliable)                   AS n_games_reliable,
        AVG(gm.average_rating) FILTER (WHERE gm.is_rating_reliable)     AS avg_rating,
        AVG(gm.weight_complexity) FILTER (WHERE gm.is_rating_reliable)  AS avg_weight,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gm.owned)           AS median_owned,
        SUM(gm.owned * b.allocation_weight)                             AS allocated_owned,
        COUNT(*) FILTER (WHERE gm.is_recent)::NUMERIC                   AS n_recent,
        COUNT(*) FILTER (WHERE gm.is_prior)::NUMERIC                    AS n_prior
    FROM bridge_game_mechanic AS b
    JOIN games AS gm ON gm.game_id = b.game_id
    GROUP BY b.mechanic_id
)
SELECT
    m.mechanic_id,
    m.mechanic_name,
    p.n_games,
    p.n_games_reliable,
    ROUND(p.avg_rating::NUMERIC, 2)                                 AS avg_rating,
    ROUND((p.avg_rating - c.avg_rating)::NUMERIC, 2)                AS rating_lift,
    ROUND(p.avg_weight::NUMERIC, 2)                                 AS avg_weight,
    p.median_owned,
    ROUND(100 * p.allocated_owned / NULLIF(c.total_owned, 0), 2)    AS owned_share_pct,
    ROUND(100 * p.n_recent / NULLIF(c.n_recent, 0), 2)              AS pct_of_recent_releases,
    ROUND(100 * p.n_prior  / NULLIF(c.n_prior, 0), 2)               AS pct_of_prior_releases,
    CASE WHEN p.n_prior >= 5 THEN
        ROUND((p.n_recent / NULLIF(c.n_recent, 0)) / (p.n_prior / c.n_prior), 2)
    END                                                             AS momentum_index
FROM per_mechanic AS p
JOIN dim_mechanic AS m ON m.mechanic_id = p.mechanic_id
CROSS JOIN catalogue AS c
ORDER BY owned_share_pct DESC NULLS LAST;
