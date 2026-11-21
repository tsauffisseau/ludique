-- Headline KPIs of the catalogue (one row) - feeds the dashboard KPI tiles.
DROP VIEW IF EXISTS mart_catalog_kpis CASCADE;
CREATE VIEW mart_catalog_kpis AS
SELECT
    COUNT(*)                                                                    AS n_games,
    COUNT(*) FILTER (WHERE g.is_rating_reliable)                                AS n_games_reliable,
    ROUND(AVG(f.average_rating) FILTER (WHERE g.is_rating_reliable)::NUMERIC, 2) AS avg_rating_reliable,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.weight_complexity)
           FILTER (WHERE g.is_rating_reliable))::NUMERIC, 2)                    AS median_weight_reliable,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY g.playing_time)                 AS median_playing_time_min,
    SUM(f.owned)                                                                AS total_owned_copies,
    SUM(f.users_rated)                                                          AS total_ratings,
    (SELECT COUNT(*) FROM dim_mechanic)                                         AS n_mechanics,
    (SELECT COUNT(*) FROM dim_category)                                         AS n_categories,
    (SELECT COUNT(*) FROM dim_designer WHERE NOT is_placeholder)                AS n_designers,
    (SELECT COUNT(*) FROM dim_publisher WHERE NOT is_placeholder)               AS n_publishers,
    (SELECT COUNT(*) FROM dim_date
      WHERE date_key IN (SELECT DISTINCT snapshot_date_key FROM fact_game_snapshot)) AS n_snapshots,
    (SELECT MAX(d.date_actual) FROM dim_date AS d
      JOIN fact_game_snapshot AS s ON s.snapshot_date_key = d.date_key)          AS latest_snapshot_date
FROM fact_game_latest AS f
JOIN dim_game AS g ON g.game_id = f.game_id;
