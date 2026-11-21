-- severity: error
-- description: ratings in [1, 10], weight in [1, 5], counters non-negative
SELECT game_id, snapshot_date_key, average_rating, bayes_average, weight_complexity, users_rated, owned
FROM fact_game_snapshot
WHERE average_rating NOT BETWEEN 1 AND 10
   OR bayes_average NOT BETWEEN 1 AND 10
   OR weight_complexity NOT BETWEEN 1 AND 5
   OR users_rated < 0 OR owned < 0 OR wishing < 0;
