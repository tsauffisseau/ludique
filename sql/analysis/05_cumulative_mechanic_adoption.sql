-- 05 · Cumulative adoption of solo and cooperative play since 2000.
-- Business question: when did solo and cooperative play take off?
-- Technique: per-game flags with BOOL_OR over the mechanic bridge, yearly counts in a
-- CTE, running totals with SUM() OVER (ORDER BY ...) and the yearly share of releases.
WITH game_flags AS (
    SELECT
        f.game_id,
        f.year_published,
        BOOL_OR(m.mechanic_name = 'Solo / Solitaire Game') AS is_solo,
        BOOL_OR(m.mechanic_name = 'Cooperative Game')      AS is_coop
    FROM fact_game_latest AS f
    LEFT JOIN bridge_game_mechanic AS b ON b.game_id = f.game_id
    LEFT JOIN dim_mechanic         AS m ON m.mechanic_id = b.mechanic_id
    WHERE f.year_published BETWEEN 2000 AND EXTRACT(YEAR FROM CURRENT_DATE)
    GROUP BY f.game_id, f.year_published
),
yearly AS (
    SELECT
        year_published,
        COUNT(*)                                     AS releases,
        COUNT(*) FILTER (WHERE is_solo)              AS solo,
        COUNT(*) FILTER (WHERE is_coop)              AS cooperative
    FROM game_flags
    GROUP BY year_published
)
SELECT
    year_published,
    releases,
    SUM(solo)        OVER (ORDER BY year_published) AS cumulative_solo_games,
    SUM(cooperative) OVER (ORDER BY year_published) AS cumulative_coop_games,
    ROUND(100.0 * solo / releases, 1)               AS pct_solo_this_year,
    ROUND(100.0 * cooperative / releases, 1)        AS pct_coop_this_year
FROM yearly
ORDER BY year_published;
