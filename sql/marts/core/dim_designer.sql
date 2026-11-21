-- Dimension: Game designer. "(Uncredited)" is kept but flagged (is_placeholder).
-- Grain = BGG designer id. SCD type 1 (upsert): names follow BGG, n_games is refreshed.
CREATE TABLE IF NOT EXISTS dim_designer (
    designer_id        INTEGER PRIMARY KEY,
    designer_name      TEXT    NOT NULL,
    is_placeholder BOOLEAN NOT NULL,
    n_games        INTEGER NOT NULL
);

INSERT INTO dim_designer (designer_id, designer_name, is_placeholder, n_games)
SELECT
    link_id,
    MIN(link_name),
    MIN(link_name) LIKE '(%)',
    COUNT(DISTINCT game_id)
FROM int_game_links
WHERE link_type = 'designer'
GROUP BY link_id
ON CONFLICT (designer_id) DO UPDATE SET
    designer_name       = EXCLUDED.designer_name,
    is_placeholder = EXCLUDED.is_placeholder,
    n_games        = EXCLUDED.n_games;
