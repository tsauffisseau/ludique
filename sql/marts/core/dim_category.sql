-- Dimension: Game category / theme (e.g. "Science Fiction").
-- Grain = BGG category id. SCD type 1 (upsert): names follow BGG, n_games is refreshed.
CREATE TABLE IF NOT EXISTS dim_category (
    category_id        INTEGER PRIMARY KEY,
    category_name      TEXT    NOT NULL,
    is_placeholder BOOLEAN NOT NULL,
    n_games        INTEGER NOT NULL
);

INSERT INTO dim_category (category_id, category_name, is_placeholder, n_games)
SELECT
    link_id,
    MIN(link_name),
    MIN(link_name) LIKE '(%)',
    COUNT(DISTINCT game_id)
FROM int_game_links
WHERE link_type = 'category'
GROUP BY link_id
ON CONFLICT (category_id) DO UPDATE SET
    category_name       = EXCLUDED.category_name,
    is_placeholder = EXCLUDED.is_placeholder,
    n_games        = EXCLUDED.n_games;
