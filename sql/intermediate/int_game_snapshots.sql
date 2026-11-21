-- Intermediate: snapshots with the dim_date surrogate key (YYYYMMDD integer).
DROP TABLE IF EXISTS int_game_snapshots CASCADE;
CREATE TABLE int_game_snapshots AS
SELECT
    s.*,
    TO_CHAR(s.snapshot_date, 'YYYYMMDD')::INTEGER AS snapshot_date_key
FROM stg_game_snapshots AS s
WHERE s.game_id IN (SELECT game_id FROM int_games);
