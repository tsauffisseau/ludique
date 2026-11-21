-- severity: error
-- description: every game of dim_game has at least one row in the snapshot fact
SELECT g.game_id, g.game_name
FROM dim_game g
WHERE NOT EXISTS (SELECT 1 FROM fact_game_snapshot f WHERE f.game_id = g.game_id);
