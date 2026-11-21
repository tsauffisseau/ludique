from datetime import date

import pandas as pd

from bgg_pipeline.transform import known_game_ids, transform

from .conftest import write_bronze


def test_silver_snapshots_validation_and_quarantine(bronze_dir, tmp_path):
    silver = tmp_path / "silver"
    stats = transform(bronze_dir, silver)

    assert stats.bronze_files == 2
    assert stats.parsed_records == 5  # 4 games on day 1 + game 1 again on day 2
    assert stats.rejected_records == 1  # Delta: rating 11
    assert stats.silver_games == 3
    assert stats.silver_snapshots == 4  # game 1 has two dated snapshots
    assert stats.snapshot_dates == 2

    games = pd.read_parquet(silver / "games.parquet").set_index("game_id")
    assert games.loc[1, "game_name"] == "Alpha (2nd edition)"  # latest snapshot wins
    assert pd.isna(games.loc[2, "year_published"])  # BGG "0" -> NULL

    snaps = pd.read_parquet(silver / "game_snapshots.parquet")
    alpha = snaps[snaps.game_id == 1].set_index("snapshot_date")
    assert alpha.loc[date(2026, 1, 1), "users_rated"] == 120
    assert alpha.loc[date(2026, 1, 2), "users_rated"] == 150

    rejected = pd.read_parquet(silver / "rejected_records.parquet")
    assert rejected.game_id.tolist() == [5]
    assert "average_rating" in rejected.reason.iloc[0]


def test_same_day_duplicates_keep_latest_fetch(tmp_path, snapshot_1, snapshot_2):
    bronze = tmp_path / "bronze"
    write_bronze(bronze, snapshot_1, 1, "run_morning")
    write_bronze(bronze / "rerun", snapshot_2, 1, "run_rerun")  # same day, game 1 again
    stats = transform(bronze, tmp_path / "silver")
    assert stats.duplicates_removed == 1
    assert stats.snapshot_dates == 1


def test_links_follow_latest_snapshot_and_valid_games_only(bronze_dir, tmp_path):
    silver = tmp_path / "silver"
    transform(bronze_dir, silver)
    links = pd.read_parquet(silver / "game_links.parquet")

    alpha_mechanics = set(links.query("game_id == 1 and link_type == 'mechanic'").link_name)
    assert alpha_mechanics == {"Hand Management"}  # "Set Collection" was dropped in run_b
    assert 5 not in set(links.game_id)  # quarantined game has no orphan links
    assert not links.duplicated(["game_id", "link_type", "link_id"]).any()
    assert known_game_ids(silver) == [1, 2, 3]
