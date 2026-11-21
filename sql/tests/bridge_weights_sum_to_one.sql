-- severity: error
-- description: allocation weights sum to 1 per game, so allocated measures never double count
SELECT 'mechanic' AS bridge, game_id, SUM(allocation_weight) AS total
FROM bridge_game_mechanic GROUP BY game_id HAVING ABS(SUM(allocation_weight) - 1) > 1e-9
UNION ALL
SELECT 'category', game_id, SUM(allocation_weight)
FROM bridge_game_category GROUP BY game_id HAVING ABS(SUM(allocation_weight) - 1) > 1e-9
UNION ALL
SELECT 'publisher', game_id, SUM(allocation_weight)
FROM bridge_game_publisher GROUP BY game_id HAVING ABS(SUM(allocation_weight) - 1) > 1e-9;
