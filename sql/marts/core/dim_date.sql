-- Dimension: calendar date of a snapshot (grain = one day). Smart key YYYYMMDD.
-- Persistent: new dates are appended, existing ones never change.
CREATE TABLE IF NOT EXISTS dim_date (
    date_key     INTEGER  PRIMARY KEY,
    date_actual  DATE     NOT NULL UNIQUE,
    year         SMALLINT NOT NULL,
    quarter      SMALLINT NOT NULL,
    month        SMALLINT NOT NULL,
    month_name   TEXT     NOT NULL,
    iso_week     SMALLINT NOT NULL,
    day_of_week  SMALLINT NOT NULL,  -- ISO: 1 = Monday
    day_name     TEXT     NOT NULL,
    is_weekend   BOOLEAN  NOT NULL
);

INSERT INTO dim_date
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER,
    d,
    EXTRACT(YEAR FROM d),
    EXTRACT(QUARTER FROM d),
    EXTRACT(MONTH FROM d),
    TRIM(TO_CHAR(d, 'Month')),
    EXTRACT(WEEK FROM d),
    EXTRACT(ISODOW FROM d),
    TRIM(TO_CHAR(d, 'Day')),
    EXTRACT(ISODOW FROM d) IN (6, 7)
FROM (
    SELECT GENERATE_SERIES(MIN(snapshot_date), MAX(snapshot_date), INTERVAL '1 day')::DATE AS d
    FROM int_game_snapshots
) AS calendar
WHERE d IS NOT NULL
ON CONFLICT (date_key) DO NOTHING;
