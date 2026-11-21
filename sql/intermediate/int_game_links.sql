-- Intermediate: links enriched with an allocation weight for N-N relationships.
--
-- A game with 4 mechanics contributes 1/4 of its "owned" copies to each mechanic.
-- Summing allocated measures over a bridge therefore never double counts: the
-- allocated total over all mechanics equals the catalogue total.
DROP TABLE IF EXISTS int_game_links CASCADE;
CREATE TABLE int_game_links AS
SELECT
    l.game_id,
    l.link_type,
    l.link_id,
    l.link_name,
    COUNT(*) OVER (PARTITION BY l.game_id, l.link_type)               AS n_links_of_type,
    1.0 / COUNT(*) OVER (PARTITION BY l.game_id, l.link_type)         AS allocation_weight
FROM stg_game_links AS l
WHERE l.game_id IN (SELECT game_id FROM int_games);
