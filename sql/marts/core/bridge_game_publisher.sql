-- Bridge: resolves the N-N relationship game <-> publisher.
-- allocation_weight = 1 / (number of publishers of the game): multiply additive measures
-- (owned copies...) by it to split them across members without double counting.
-- Rows of the games present in this load are replaced (delete + insert).
CREATE TABLE IF NOT EXISTS bridge_game_publisher (
    game_id            INTEGER NOT NULL REFERENCES dim_game (game_id),
    publisher_id            INTEGER NOT NULL REFERENCES dim_publisher (publisher_id),
    allocation_weight  NUMERIC NOT NULL CHECK (allocation_weight > 0 AND allocation_weight <= 1),
    PRIMARY KEY (game_id, publisher_id)
);

DELETE FROM bridge_game_publisher WHERE game_id IN (SELECT game_id FROM int_games);

INSERT INTO bridge_game_publisher (game_id, publisher_id, allocation_weight)
SELECT game_id, link_id, allocation_weight
FROM int_game_links
WHERE link_type = 'publisher';
