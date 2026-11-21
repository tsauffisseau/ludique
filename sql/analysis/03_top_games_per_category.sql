-- 03 · Top 3 games per category.
-- Business question: which reference titles will a newcomer be compared with in each theme?
-- Technique: chained CTEs + ROW_NUMBER() partitioned by category. The Bayesian average is
-- the ranking metric: like the BGG ranking, it penalises games with few votes.
WITH rated AS (
    SELECT b.category_id, f.game_id, f.bayes_average, f.users_rated
    FROM bridge_game_category AS b
    JOIN fact_game_latest AS f ON f.game_id = b.game_id
    WHERE f.bayes_average IS NOT NULL
),
ranked AS (
    SELECT
        r.*,
        ROW_NUMBER() OVER (PARTITION BY r.category_id ORDER BY r.bayes_average DESC) AS position,
        COUNT(*)     OVER (PARTITION BY r.category_id)                               AS n_ranked_games
    FROM rated AS r
)
SELECT
    c.category_name,
    k.position,
    g.game_name,
    ROUND(k.bayes_average::NUMERIC, 2) AS geek_rating,
    k.users_rated
FROM ranked AS k
JOIN dim_category AS c ON c.category_id = k.category_id
JOIN dim_game     AS g ON g.game_id = k.game_id
WHERE k.position <= 3 AND k.n_ranked_games >= 20
ORDER BY c.category_name, k.position;
