-- Convenience view: the latest snapshot of each game (same columns as the fact).
-- "State of the market" marts read this view; trend analyses read fact_game_snapshot.
DROP VIEW IF EXISTS fact_game_latest CASCADE;
CREATE VIEW fact_game_latest AS
SELECT DISTINCT ON (f.game_id) f.*
FROM fact_game_snapshot AS f
ORDER BY f.game_id, f.snapshot_date_key DESC;
