-- Example Athena queries on the lake (serverless, pay-per-scan: Parquet keeps scans small).

-- 1. Bronze audit: how many raw responses per ingestion day, and how many were not HTTP 200?
SELECT ingestion_date,
       COUNT(*)                                  AS responses,
       COUNT_IF(http_status <> 200)              AS non_200,
       MIN(fetched_at)                           AS first_call,
       MAX(fetched_at)                           AS last_call
FROM bgg_lake.bronze_bgg_thing
GROUP BY ingestion_date
ORDER BY ingestion_date;

-- 2. Best-rated mechanics on the latest snapshot (same logic as the PostgreSQL mart).
WITH latest AS (
    SELECT *
    FROM bgg_lake.fact_game_snapshot
    WHERE snapshot_date_key = (SELECT MAX(snapshot_date_key) FROM bgg_lake.fact_game_snapshot)
)
SELECT m.mechanic_name,
       COUNT(*)                         AS n_games,
       ROUND(AVG(f.average_rating), 2)  AS avg_rating
FROM latest AS f
JOIN bgg_lake.bridge_game_mechanic AS b ON b.game_id = f.game_id
JOIN bgg_lake.dim_mechanic        AS m ON m.mechanic_id = b.mechanic_id
WHERE f.users_rated >= 30
GROUP BY m.mechanic_name
HAVING COUNT(*) >= 15
ORDER BY avg_rating DESC
LIMIT 15;
