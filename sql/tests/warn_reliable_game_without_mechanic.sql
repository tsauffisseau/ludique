-- severity: warn
-- description: well-rated games (>= 30 ratings) with no mechanic assigned - invisible in mechanic marts
SELECT game_id, game_name
FROM dim_game
WHERE is_rating_reliable AND n_mechanics = 0;
