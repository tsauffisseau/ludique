-- Dimension: Game mechanic (e.g. "Deck, Bag, and Pool Building").
-- Grain = BGG mechanic id. SCD type 1 (upsert): names follow BGG, n_games is refreshed.
CREATE TABLE IF NOT EXISTS dim_mechanic (
    mechanic_id        INTEGER PRIMARY KEY,
    mechanic_name      TEXT    NOT NULL,
    is_placeholder BOOLEAN NOT NULL,
    n_games        INTEGER NOT NULL
);

INSERT INTO dim_mechanic (mechanic_id, mechanic_name, is_placeholder, n_games)
SELECT
    link_id,
    MIN(link_name),
    MIN(link_name) LIKE '(%)',
    COUNT(DISTINCT game_id)
FROM int_game_links
WHERE link_type = 'mechanic'
GROUP BY link_id
ON CONFLICT (mechanic_id) DO UPDATE SET
    mechanic_name       = EXCLUDED.mechanic_name,
    is_placeholder = EXCLUDED.is_placeholder,
    n_games        = EXCLUDED.n_games;
