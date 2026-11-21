-- severity: error
-- description: dimension keys are unique (also enforced by PRIMARY KEY constraints)
SELECT 'dim_game' AS dim, game_id AS id FROM dim_game GROUP BY game_id HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_mechanic', mechanic_id FROM dim_mechanic GROUP BY mechanic_id HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_category', category_id FROM dim_category GROUP BY category_id HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_designer', designer_id FROM dim_designer GROUP BY designer_id HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_publisher', publisher_id FROM dim_publisher GROUP BY publisher_id HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_year', year_published FROM dim_year GROUP BY year_published HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_date', date_key FROM dim_date GROUP BY date_key HAVING COUNT(*) > 1;
