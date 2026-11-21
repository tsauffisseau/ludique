-- severity: error
-- description: every star-schema table is populated
SELECT t.table_name
FROM (VALUES
    ('dim_game', (SELECT COUNT(*) FROM dim_game)),
    ('dim_date', (SELECT COUNT(*) FROM dim_date)),
    ('dim_year', (SELECT COUNT(*) FROM dim_year)),
    ('dim_mechanic', (SELECT COUNT(*) FROM dim_mechanic)),
    ('dim_category', (SELECT COUNT(*) FROM dim_category)),
    ('dim_designer', (SELECT COUNT(*) FROM dim_designer)),
    ('dim_publisher', (SELECT COUNT(*) FROM dim_publisher)),
    ('bridge_game_mechanic', (SELECT COUNT(*) FROM bridge_game_mechanic)),
    ('bridge_game_category', (SELECT COUNT(*) FROM bridge_game_category)),
    ('fact_game_snapshot', (SELECT COUNT(*) FROM fact_game_snapshot))
) AS t (table_name, n_rows)
WHERE t.n_rows = 0;
