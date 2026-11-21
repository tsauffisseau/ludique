-- severity: error
-- description: every fact row points to an existing game, snapshot date and year (referential integrity)
SELECT f.game_id, f.snapshot_date_key, 'missing dim_game' AS issue
FROM fact_game_snapshot f LEFT JOIN dim_game g ON g.game_id = f.game_id WHERE g.game_id IS NULL
UNION ALL
SELECT f.game_id, f.snapshot_date_key, 'missing dim_date'
FROM fact_game_snapshot f LEFT JOIN dim_date d ON d.date_key = f.snapshot_date_key WHERE d.date_key IS NULL
UNION ALL
SELECT f.game_id, f.snapshot_date_key, 'missing dim_year'
FROM fact_game_snapshot f LEFT JOIN dim_year y ON y.year_published = f.year_published
WHERE y.year_published IS NULL;
