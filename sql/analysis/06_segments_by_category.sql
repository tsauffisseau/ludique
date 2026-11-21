-- 06 · Which themes characterise each K-means segment?
-- Business question: for each segment found by clustering, which categories over-index?
-- Technique: the ML output joined back to the star schema, shares computed with window
-- SUMs over different partitions, and a lift (share in segment / share overall) ranked
-- with ROW_NUMBER inside each segment.
WITH per_pair AS (
    SELECT s.segment_name, c.category_name, COUNT(*) AS n_games
    FROM game_clusters AS s
    JOIN bridge_game_category AS b ON b.game_id = s.game_id
    JOIN dim_category         AS c ON c.category_id = b.category_id
    GROUP BY s.segment_name, c.category_name
),
shares AS (
    SELECT
        *,
        n_games::NUMERIC / SUM(n_games) OVER (PARTITION BY segment_name)   AS share_in_segment,
        SUM(n_games) OVER (PARTITION BY category_name)::NUMERIC
            / SUM(n_games) OVER ()                                         AS share_overall
    FROM per_pair
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY segment_name ORDER BY share_in_segment / share_overall DESC) AS r
    FROM shares
    WHERE n_games >= 5
)
SELECT
    segment_name,
    category_name,
    n_games,
    ROUND(100 * share_in_segment, 1)           AS pct_of_segment,
    ROUND(share_in_segment / share_overall, 2) AS lift
FROM ranked
WHERE r <= 3
ORDER BY segment_name, r;
