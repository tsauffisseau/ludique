-- 04 · Publisher leaderboard.
-- Business question: which publishers combine a large footprint and consistent quality?
-- Technique: aggregation through the publisher bridge (placeholder publishers excluded),
-- allocated owned copies (no double counting of co-published games), DENSE_RANK and a
-- quality-consistency measure (share of games rated 7+).
SELECT
    p.publisher_name,
    COUNT(*)                                                                  AS n_games,
    ROUND(AVG(f.average_rating)::NUMERIC, 2)                                  AS avg_rating,
    ROUND(100.0 * COUNT(*) FILTER (WHERE f.average_rating >= 7) / COUNT(*))   AS pct_games_rated_7_plus,
    ROUND(SUM(f.owned * b.allocation_weight))                                 AS allocated_owned_copies,
    DENSE_RANK() OVER (ORDER BY AVG(f.average_rating) DESC)                   AS quality_rank
FROM bridge_game_publisher AS b
JOIN dim_publisher    AS p ON p.publisher_id = b.publisher_id
JOIN fact_game_latest AS f ON f.game_id = b.game_id
JOIN dim_game         AS g ON g.game_id = b.game_id
WHERE g.is_rating_reliable
  AND NOT p.is_placeholder
GROUP BY p.publisher_name
HAVING COUNT(*) >= 5
ORDER BY allocated_owned_copies DESC
LIMIT 10;
