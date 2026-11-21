-- Dimension: Game publisher ("éditeur"). "(Self-Published)", "(Web published)", "(Unknown)" are kept but flagged (is_placeholder).
-- Grain = BGG publisher id. SCD type 1 (upsert): names follow BGG, n_games is refreshed.
CREATE TABLE IF NOT EXISTS dim_publisher (
    publisher_id        INTEGER PRIMARY KEY,
    publisher_name      TEXT    NOT NULL,
    is_placeholder BOOLEAN NOT NULL,
    n_games        INTEGER NOT NULL
);

INSERT INTO dim_publisher (publisher_id, publisher_name, is_placeholder, n_games)
SELECT
    link_id,
    MIN(link_name),
    MIN(link_name) LIKE '(%)',
    COUNT(DISTINCT game_id)
FROM int_game_links
WHERE link_type = 'publisher'
GROUP BY link_id
ON CONFLICT (publisher_id) DO UPDATE SET
    publisher_name       = EXCLUDED.publisher_name,
    is_placeholder = EXCLUDED.is_placeholder,
    n_games        = EXCLUDED.n_games;
