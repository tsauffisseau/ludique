-- severity: warn
-- description: games announced for a future year (not yet released, excluded from market marts)
SELECT f.game_id, g.game_name, f.year_published
FROM fact_game_latest f JOIN dim_game g ON g.game_id = f.game_id
WHERE f.year_published > EXTRACT(YEAR FROM CURRENT_DATE);
