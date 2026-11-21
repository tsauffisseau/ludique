-- severity: warn
-- description: rank moved by more than 5 000 places between two consecutive snapshots (re-check the source)
SELECT game_name, previous_rank, latest_rank, rank_change
FROM mart_rank_movers
WHERE ABS(rank_change) > 5000;
