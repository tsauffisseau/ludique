-- severity: warn
-- description: playing time above 24 h (monster wargames or data entry errors - review before averaging)
SELECT game_id, game_name, playing_time
FROM dim_game
WHERE playing_time > 1440
ORDER BY playing_time DESC;
