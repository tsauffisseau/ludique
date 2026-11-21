-- severity: warn
-- description: min_players greater than max_players (source data entry error on BGG)
SELECT game_id, game_name, min_players, max_players
FROM dim_game
WHERE min_players > max_players;
