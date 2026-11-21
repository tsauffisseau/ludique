-- severity: error
-- description: fact_game_snapshot has exactly one row per game per snapshot date (declared grain)
SELECT game_id, snapshot_date_key, COUNT(*) AS n
FROM fact_game_snapshot
GROUP BY game_id, snapshot_date_key
HAVING COUNT(*) > 1;
