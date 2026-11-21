-- severity: error
-- description: every bridge row points to an existing game and dimension member
SELECT 'mechanic' AS bridge, b.game_id, b.mechanic_id AS member_id
FROM bridge_game_mechanic b
LEFT JOIN dim_game g ON g.game_id = b.game_id
LEFT JOIN dim_mechanic m ON m.mechanic_id = b.mechanic_id
WHERE g.game_id IS NULL OR m.mechanic_id IS NULL
UNION ALL
SELECT 'category', b.game_id, b.category_id
FROM bridge_game_category b
LEFT JOIN dim_game g ON g.game_id = b.game_id
LEFT JOIN dim_category c ON c.category_id = b.category_id
WHERE g.game_id IS NULL OR c.category_id IS NULL
UNION ALL
SELECT 'publisher', b.game_id, b.publisher_id
FROM bridge_game_publisher b
LEFT JOIN dim_game g ON g.game_id = b.game_id
LEFT JOIN dim_publisher p ON p.publisher_id = b.publisher_id
WHERE g.game_id IS NULL OR p.publisher_id IS NULL;
