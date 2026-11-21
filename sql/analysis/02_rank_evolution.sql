-- 02 · Rank evolution over the weekly snapshots.
-- Business question: which games are gaining momentum in the BGG ranking right now?
-- Technique: LAG / FIRST_VALUE over a named WINDOW on the periodic snapshot fact,
-- then each game's latest snapshot kept with ROW_NUMBER.
WITH history AS (
    SELECT
        g.game_name,
        d.date_actual,
        f.bgg_rank,
        f.users_rated,
        LAG(f.bgg_rank)          OVER w AS previous_rank,
        FIRST_VALUE(f.bgg_rank)  OVER w AS first_rank,
        COUNT(*)                 OVER (PARTITION BY f.game_id) AS n_snapshots,
        ROW_NUMBER()             OVER (PARTITION BY f.game_id ORDER BY d.date_actual DESC) AS recency
    FROM fact_game_snapshot AS f
    JOIN dim_date AS d ON d.date_key = f.snapshot_date_key
    JOIN dim_game AS g ON g.game_id = f.game_id
    WHERE f.bgg_rank IS NOT NULL
    WINDOW w AS (PARTITION BY f.game_id ORDER BY d.date_actual)
)
SELECT
    game_name,
    n_snapshots,
    first_rank,
    previous_rank,
    bgg_rank                   AS latest_rank,
    first_rank - bgg_rank      AS places_gained_since_first_snapshot
FROM history
WHERE recency = 1 AND n_snapshots > 1
ORDER BY places_gained_since_first_snapshot DESC
LIMIT 10;
