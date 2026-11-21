"""End-to-end on PostgreSQL: Bronze fixture -> Silver -> Gold star schema -> quality gate."""

from __future__ import annotations

import psycopg
import pytest

from bgg_pipeline.data_quality import run_quality
from bgg_pipeline.load import build_warehouse, model_files
from bgg_pipeline.transform import transform

from .conftest import SQL_DIR, write_bronze


@pytest.fixture
def warehouse(bronze_dir, tmp_path, pg_dsn):
    silver = tmp_path / "silver"
    transform(bronze_dir, silver)
    build_warehouse(silver, pg_dsn, SQL_DIR)
    return silver, pg_dsn


def fetch(dsn: str, sql: str):
    with psycopg.connect(dsn) as con:
        return con.execute(sql).fetchall()


def test_models_run_in_dependency_order():
    order = [p.stem for _, p in model_files(SQL_DIR)]
    assert order.index("int_games") < order.index("int_game_links")
    assert order.index("dim_game") < order.index("bridge_game_mechanic")
    assert order.index("dim_date") < order.index("fact_game_snapshot")
    assert order.index("fact_game_snapshot") < order.index("fact_game_latest")
    assert order.index("fact_game_latest") < order.index("mart_top_mechanics_trends")


def test_star_schema_content(warehouse):
    _, dsn = warehouse
    assert fetch(dsn, "select count(*) from dw.dim_game") == [(3,)]
    # Grain game x date: game 1 has two snapshots
    assert fetch(dsn, "select count(*) from dw.fact_game_snapshot") == [(4,)]
    assert fetch(dsn, "select date_key from dw.dim_date order by 1") == [(20260101,), (20260102,)]
    # Unknown year -> Kimball unknown member 0, which exists in dim_year
    assert fetch(dsn, "select distinct year_published from dw.fact_game_snapshot where game_id = 2") == [(0,)]
    assert fetch(dsn, "select decade_label from dw.dim_year where year_published = 0") == [("Unknown",)]
    # Publisher dimension and bridge
    assert fetch(dsn, "select publisher_name from dw.dim_publisher") == [("Acme Games",)]
    # Bridge allocation: Gamma has 2 mechanics -> 0.5 each
    weights = fetch(dsn, "select allocation_weight from dw.bridge_game_mechanic where game_id = 3")
    assert [float(w) for (w,) in weights] == [0.5, 0.5]
    # Latest view keeps one row per game, with the most recent figures
    assert fetch(dsn, "select users_rated from dw.fact_game_latest where game_id = 1") == [(150,)]


def test_incremental_load_appends_new_snapshots_only(tmp_path, pg_dsn, snapshot_1, snapshot_2):
    bronze, silver = tmp_path / "bronze", tmp_path / "silver"
    write_bronze(bronze, snapshot_1, 1, "run_a")
    transform(bronze, silver)
    build_warehouse(silver, pg_dsn, SQL_DIR)
    first = fetch(
        pg_dsn, "select game_id, snapshot_date_key, loaded_at from dw.fact_game_snapshot order by 1, 2"
    )
    assert len(first) == 3

    write_bronze(bronze, snapshot_2, 2, "run_b")  # next week's refresh
    transform(bronze, silver)
    build_warehouse(silver, pg_dsn, SQL_DIR)
    second = fetch(
        pg_dsn, "select game_id, snapshot_date_key, loaded_at from dw.fact_game_snapshot order by 1, 2"
    )
    assert len(second) == 4
    # History before the watermark is never reloaded: the day-1 rows are untouched.
    assert [r for r in second if r[1] == 20260101] == first

    build_warehouse(silver, pg_dsn, SQL_DIR)  # re-run with nothing new: idempotent
    assert fetch(pg_dsn, "select count(*) from dw.fact_game_snapshot") == [(4,)]


def test_full_refresh_rebuilds_history(warehouse, tmp_path):
    silver, dsn = warehouse
    build_warehouse(silver, dsn, SQL_DIR, full_refresh=True)
    assert fetch(dsn, "select count(*) from dw.fact_game_snapshot") == [(4,)]


def test_business_marts(warehouse):
    _, dsn = warehouse
    mech = fetch(
        dsn,
        "select n_games, n_games_reliable, avg_rating from marts.mart_top_mechanics_trends "
        "where mechanic_name = 'Hand Management'",
    )
    assert mech[0][:2] == (2, 2)
    assert float(mech[0][2]) == pytest.approx((7.6 + 8.1) / 2, abs=0.01)
    assert fetch(dsn, "select n_games, n_games_reliable, n_snapshots from marts.mart_catalog_kpis") == [
        (3, 2, 2)
    ]
    decades = [r[0] for r in fetch(dsn, "select decade_label from marts.mart_decade_trends")]
    assert decades == ["2010s", "2020s"]  # unknown year excluded from trends
    movers = fetch(dsn, "select game_name, rank_change from marts.mart_rank_movers")
    assert movers == [("Alpha (2nd edition)", 100)]  # rank 1500 -> 1400


def test_analysis_queries_run(warehouse):
    from bgg_pipeline.load import query_df

    _, dsn = warehouse
    for path in sorted((SQL_DIR / "analysis").glob("*.sql")):
        if "segments" in path.stem:
            continue  # needs the clustering output (too few games in the fixture)
        query_df(dsn, path.read_text(encoding="utf-8"))  # must not raise


def test_quality_gate_passes_and_flags_soft_anomalies(warehouse, tmp_path):
    silver, dsn = warehouse
    checks = {c.name: c for c in run_quality(silver, dsn, SQL_DIR / "tests", tmp_path / "reports")}
    assert not [c for c in checks.values() if c.status == "FAIL"]
    assert checks["warn_player_count_inconsistent"].failing_rows == 1  # Beta: 4 > 2
    assert checks["warn_extreme_playing_time"].failing_rows == 1  # Gamma: 2000 min
    assert checks["silver_quarantine"].failing_rows == 1  # Delta: rating 11
    assert (tmp_path / "reports" / "data_quality_report.md").exists()


def test_quality_gate_blocks_on_broken_allocation(warehouse, tmp_path):
    silver, dsn = warehouse
    with psycopg.connect(dsn) as con:
        con.execute("update dw.bridge_game_mechanic set allocation_weight = 0.9 where game_id = 3")
    checks = run_quality(silver, dsn, SQL_DIR / "tests", tmp_path / "reports")
    assert "bridge_weights_sum_to_one" in {c.name for c in checks if c.status == "FAIL"}


def test_constraints_reject_orphans(warehouse):
    _, dsn = warehouse
    with pytest.raises(psycopg.errors.ForeignKeyViolation), psycopg.connect(dsn) as con:
        con.execute("insert into dw.bridge_game_mechanic values (999999, 2040, 1)")
