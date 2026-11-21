-- History - Which games are climbing or falling in the BGG ranking?
-- Compares each game's rank and rating between its two most recent snapshots using
-- window functions over the periodic snapshot fact (LAG over snapshot dates).
-- Positive rank_change = the game climbed (rank 1500 -> 1400 = +100).
DROP VIEW IF EXISTS mart_rank_movers CASCADE;
CREATE VIEW mart_rank_movers AS
WITH history AS (
    SELECT
        f.game_id,
        d.date_actual,
        f.bgg_rank,
        f.average_rating,
        f.users_rated,
        LAG(f.bgg_rank)       OVER w AS previous_rank,
        LAG(f.average_rating) OVER w AS previous_rating,
        LAG(f.users_rated)    OVER w AS previous_users_rated,
        LAG(d.date_actual)    OVER w AS previous_date,
        ROW_NUMBER()          OVER (PARTITION BY f.game_id ORDER BY d.date_actual DESC) AS recency
    FROM fact_game_snapshot AS f
    JOIN dim_date AS d ON d.date_key = f.snapshot_date_key
    WINDOW w AS (PARTITION BY f.game_id ORDER BY d.date_actual)
)
SELECT
    g.game_name,
    h.game_id,
    h.previous_date,
    h.date_actual                                         AS latest_date,
    h.previous_rank,
    h.bgg_rank                                            AS latest_rank,
    h.previous_rank - h.bgg_rank                          AS rank_change,
    ROUND((h.average_rating - h.previous_rating)::NUMERIC, 3) AS rating_change,
    h.users_rated - h.previous_users_rated                AS new_ratings
FROM history AS h
JOIN dim_game AS g ON g.game_id = h.game_id
WHERE h.recency = 1
  AND h.previous_rank IS NOT NULL
  AND h.bgg_rank IS NOT NULL;
