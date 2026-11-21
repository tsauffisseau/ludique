-- Q4 - Where are the under-served niches? Mechanic x category combinations that players
--      rate highly and wishlist a lot, but that few publishers have addressed.
--
-- opportunity_score = z(quality) + z(unmet demand) - z(supply)
--   quality       : average rating of reliable games in the niche
--   unmet demand  : ln(1 + wishlists / owned copies) - people who want it but don't have it.
--                   The ratio is heavy-tailed, hence the log.
--   supply        : ln(number of games) - the sample is a uniform draw of BGG ids,
--                   so counts are proportional to the real catalogue.
-- Robustness: each z-score is clipped to [-3, 3] so a single outlier cannot dominate,
-- unreleased games are excluded (crowdfunding wishlists are not market demand yet), and
-- niches need >= 3 reliable games to be scored (minimum statistical support).
DROP VIEW IF EXISTS mart_niche_opportunities CASCADE;
CREATE VIEW mart_niche_opportunities AS
WITH pairs AS (
    SELECT bm.mechanic_id, bc.category_id, f.game_id, f.average_rating, f.owned, f.wishing,
           g.is_rating_reliable
    FROM bridge_game_mechanic AS bm
    JOIN bridge_game_category AS bc ON bc.game_id = bm.game_id
    JOIN fact_game_latest     AS f  ON f.game_id  = bm.game_id
    JOIN dim_game             AS g  ON g.game_id  = bm.game_id
    WHERE g.is_released
),
niches AS (
    SELECT
        mechanic_id,
        category_id,
        COUNT(*)                                                AS n_games,
        COUNT(*) FILTER (WHERE is_rating_reliable)              AS n_games_reliable,
        AVG(average_rating) FILTER (WHERE is_rating_reliable)   AS avg_rating,
        SUM(wishing)::DOUBLE PRECISION / NULLIF(SUM(owned), 0)  AS wish_to_own_ratio,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY owned)      AS median_owned
    FROM pairs
    GROUP BY mechanic_id, category_id
    HAVING COUNT(*) FILTER (WHERE is_rating_reliable) >= 3
),
signals AS (
    SELECT *, LN(1 + COALESCE(wish_to_own_ratio, 0)) AS demand, LN(n_games) AS supply
    FROM niches
),
scored AS (
    SELECT
        *,
        GREATEST(-3, LEAST(3, (avg_rating - AVG(avg_rating) OVER ())
            / NULLIF(STDDEV_SAMP(avg_rating) OVER (), 0)))          AS z_quality,
        GREATEST(-3, LEAST(3, (demand - AVG(demand) OVER ())
            / NULLIF(STDDEV_SAMP(demand) OVER (), 0)))              AS z_demand,
        GREATEST(-3, LEAST(3, (supply - AVG(supply) OVER ())
            / NULLIF(STDDEV_SAMP(supply) OVER (), 0)))              AS z_supply
    FROM signals
)
SELECT
    m.mechanic_name,
    c.category_name,
    s.n_games,
    s.n_games_reliable,
    ROUND(s.avg_rating::NUMERIC, 2)                                     AS avg_rating,
    ROUND(s.wish_to_own_ratio::NUMERIC, 3)                              AS wish_to_own_ratio,
    s.median_owned,
    ROUND(s.z_quality::NUMERIC, 2)                                      AS z_quality,
    ROUND(s.z_demand::NUMERIC, 2)                                       AS z_demand,
    ROUND(s.z_supply::NUMERIC, 2)                                       AS z_supply,
    ROUND((s.z_quality + s.z_demand - s.z_supply)::NUMERIC, 2)          AS opportunity_score,
    RANK() OVER (ORDER BY s.z_quality + s.z_demand - s.z_supply DESC)   AS opportunity_rank,
    s.mechanic_id,
    s.category_id
FROM scored AS s
JOIN dim_mechanic AS m ON m.mechanic_id = s.mechanic_id
JOIN dim_category AS c ON c.category_id = s.category_id
ORDER BY opportunity_rank;
