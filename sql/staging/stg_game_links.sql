-- Staging: game <-> taxonomy links (mechanic, category, designer, publisher, family, artist).
DROP VIEW IF EXISTS stg_game_links CASCADE;
CREATE VIEW stg_game_links AS
SELECT game_id, link_type, link_id, link_name
FROM silver.game_links;
