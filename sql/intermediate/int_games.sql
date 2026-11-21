-- Intermediate: business rules computed once, reused by every downstream model.
--
-- * is_rating_reliable : BGG itself only ranks games with >= 30 ratings. Below that an
--   average is noise (one enthusiastic designer + friends = 9.8/10), so every quality
--   metric in the marts filters on this flag. Volume/supply metrics use all games.
-- * is_released : games announced for a future year are not on the market yet. Their
--   crowdfunding wishlists (hundreds of wishes, a handful of copies) would distort any
--   supply/demand metric, so market marts exclude them. Unknown year = assumed released.
-- * Buckets carry a sortable numeric prefix for BI tools.
DROP TABLE IF EXISTS int_games CASCADE;
CREATE TABLE int_games AS
SELECT
    g.*,
    g.users_rated >= 30 AS is_rating_reliable,
    COALESCE(g.year_published <= EXTRACT(YEAR FROM CURRENT_DATE), TRUE) AS is_released,
    g.min_players = 1   AS supports_solo,
    CASE
        WHEN g.weight_complexity IS NULL THEN '0. Unknown'
        WHEN g.weight_complexity < 1.5  THEN '1. Light (1.0-1.5)'
        WHEN g.weight_complexity < 2.25 THEN '2. Medium-light (1.5-2.25)'
        WHEN g.weight_complexity < 3.0  THEN '3. Medium (2.25-3.0)'
        WHEN g.weight_complexity < 3.75 THEN '4. Medium-heavy (3.0-3.75)'
        ELSE                                 '5. Heavy (3.75-5.0)'
    END AS weight_bucket,
    CASE
        WHEN g.playing_time IS NULL THEN '0. Unknown'
        WHEN g.playing_time <= 30   THEN '1. Filler (<= 30 min)'
        WHEN g.playing_time <= 60   THEN '2. Short (31-60 min)'
        WHEN g.playing_time <= 120  THEN '3. Standard (1-2 h)'
        WHEN g.playing_time <= 240  THEN '4. Long (2-4 h)'
        ELSE                             '5. Epic (> 4 h)'
    END AS playtime_bucket,
    CASE
        WHEN g.max_players IS NULL THEN '0. Unknown'
        WHEN g.max_players = 1     THEN '1. Solo only'
        WHEN g.max_players = 2     THEN '2. Up to 2 players'
        WHEN g.max_players <= 4    THEN '3. Up to 4 players'
        WHEN g.max_players <= 6    THEN '4. Up to 6 players'
        ELSE                            '5. 7+ players'
    END AS player_count_profile
FROM stg_games AS g;
