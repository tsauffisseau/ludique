-- severity: error
-- description: a snapshot with zero ratings must not carry an average rating
SELECT game_id, snapshot_date_key, users_rated, average_rating
FROM fact_game_snapshot
WHERE users_rated = 0 AND average_rating IS NOT NULL;
