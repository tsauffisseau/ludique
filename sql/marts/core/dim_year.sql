-- Dimension: publication year, with decade and market-era hierarchies.
-- Kimball "unknown member": year_published = 0 stands for "year not provided", so the
-- fact table never carries a NULL foreign key and inner joins never drop games.
CREATE TABLE IF NOT EXISTS dim_year (
    year_published  INTEGER PRIMARY KEY,
    decade          INTEGER,
    decade_label    TEXT    NOT NULL,
    market_era      TEXT    NOT NULL,
    is_known        BOOLEAN NOT NULL
);

INSERT INTO dim_year
SELECT
    year_published,
    (FLOOR(year_published / 10.0) * 10)::INTEGER,
    CASE
        WHEN year_published < 1950 THEN 'Before 1950'
        ELSE ((FLOOR(year_published / 10.0) * 10)::INTEGER)::TEXT || 's'
    END,
    CASE
        WHEN year_published < 1980 THEN '1. Classic & traditional (< 1980)'
        WHEN year_published < 1995 THEN '2. Hobby emergence (1980-1994)'
        WHEN year_published < 2010 THEN '3. Eurogame era (1995-2009)'
        WHEN year_published < 2020 THEN '4. Crowdfunding boom (2010-2019)'
        ELSE                            '5. Post-2020 market'
    END,
    TRUE
FROM (
    SELECT DISTINCT year_published FROM int_games
    WHERE year_published IS NOT NULL AND year_published <> 0
) AS years
UNION ALL
SELECT 0, NULL, 'Unknown', '0. Unknown', FALSE
ON CONFLICT (year_published) DO NOTHING;
