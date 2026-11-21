-- severity: error
-- description: bridge tables contain no duplicated (game, member) pair
SELECT 'mechanic' AS bridge, game_id, mechanic_id AS member_id FROM bridge_game_mechanic
GROUP BY game_id, mechanic_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'category', game_id, category_id FROM bridge_game_category
GROUP BY game_id, category_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'publisher', game_id, publisher_id FROM bridge_game_publisher
GROUP BY game_id, publisher_id HAVING COUNT(*) > 1;
