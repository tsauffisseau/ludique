"""Silver layer: Bronze raw XML -> typed, validated, deduplicated Parquet tables.

Outputs (``data/silver/``)
--------------------------
* ``games.parquet``            one row per game: its latest valid snapshot (descriptive data)
* ``game_snapshots.parquet``   one row per game per snapshot date: the time-varying metrics
                               (ratings, rank, owners...) that feed the history fact table
* ``game_links.parquet``       game <-> mechanic/category/designer/publisher (N-N, long format)
* ``rejected_records.parquet`` quarantine: records breaking a hard contract + reason
* ``_transform_stats.json``    lineage counters consumed by the data-quality report
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pydantic import ValidationError

from .parse import parse_payload
from .schemas import GameLink, GameRecord

logger = logging.getLogger(__name__)

SNAPSHOT_COLUMNS = [
    "game_id",
    "snapshot_date",
    "users_rated",
    "average_rating",
    "bayes_average",
    "rating_stddev",
    "bgg_rank",
    "num_weights",
    "weight_complexity",
    "owned",
    "trading",
    "wanting",
    "wishing",
    "num_comments",
    "source_fetched_at",
]


@dataclass
class TransformStats:
    bronze_files: int = 0
    bronze_responses: int = 0
    parsed_records: int = 0
    duplicates_removed: int = 0
    rejected_records: int = 0
    silver_games: int = 0
    silver_snapshots: int = 0
    snapshot_dates: int = 0
    silver_links: int = 0


def read_bronze(bronze_dir: Path) -> tuple[pd.DataFrame, int]:
    files = sorted(bronze_dir.rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"Bronze zone is empty: {bronze_dir}. Run the extract step first.")
    cols = ["run_id", "fetched_at", "http_status", "payload"]
    frames = [pq.ParquetFile(f).read(columns=cols).to_pandas() for f in files]
    return pd.concat(frames, ignore_index=True), len(files)


def known_game_ids(silver_dir: Path) -> list[int]:
    """Ids already in Silver - used by the weekly refresh to re-snapshot known games only."""
    path = silver_dir / "games.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No Silver games at {path}: run a full load before a refresh.")
    return sorted(pd.read_parquet(path, columns=["game_id"]).game_id.astype(int).tolist())


def _validation_reason(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())


def transform(bronze_dir: Path, silver_dir: Path) -> TransformStats:
    stats = TransformStats()
    bronze, stats.bronze_files = read_bronze(bronze_dir)
    bronze = bronze[bronze["http_status"] == 200]
    stats.bronze_responses = len(bronze)

    records, links = [], []
    for row in bronze.itertuples(index=False):
        recs, lnks = parse_payload(row.payload)
        for r in recs:
            r["source_run_id"] = row.run_id
            r["source_fetched_at"] = row.fetched_at
        records.extend(recs)
        links.extend({**link, "source_fetched_at": row.fetched_at} for link in lnks)
    stats.parsed_records = len(records)

    # --- Deduplication: one snapshot per game per day (the latest fetch of the day wins).
    raw = pd.DataFrame(records).sort_values("source_fetched_at")
    raw["snapshot_date"] = raw["source_fetched_at"].dt.tz_convert("UTC").dt.date
    deduped = raw.drop_duplicates(["game_id", "snapshot_date"], keep="last")
    stats.duplicates_removed = len(raw) - len(deduped)

    # --- Contract validation: valid rows go to Silver, the rest to quarantine.
    valid, rejected = [], []
    for rec in deduped.to_dict("records"):
        rec = {k: (None if not isinstance(v, (list, dict)) and pd.isna(v) else v) for k, v in rec.items()}
        snapshot_date = rec.pop("snapshot_date")
        try:
            valid.append({**GameRecord.model_validate(rec).model_dump(), "snapshot_date": snapshot_date})
        except ValidationError as exc:
            rejected.append(
                {
                    "game_id": rec.get("game_id"),
                    "game_name": rec.get("game_name"),
                    "snapshot_date": snapshot_date,
                    "reason": _validation_reason(exc),
                    "raw_record": json.dumps(rec, default=str, ensure_ascii=False),
                }
            )
    stats.rejected_records = len(rejected)

    snapshots_all = pd.DataFrame(valid)
    int_cols = [c for c, f in GameRecord.model_fields.items() if f.annotation in (int, int | None)]
    snapshots_all[int_cols] = snapshots_all[int_cols].astype("Int64")

    # Descriptive attributes: the latest valid snapshot of each game.
    games = snapshots_all.sort_values("source_fetched_at").drop_duplicates("game_id", keep="last")
    games = games.drop(columns="snapshot_date")
    stats.silver_games = len(games)

    snapshots = snapshots_all[SNAPSHOT_COLUMNS].sort_values(["game_id", "snapshot_date"])
    stats.silver_snapshots = len(snapshots)
    stats.snapshot_dates = snapshots.snapshot_date.nunique()

    # Links of the latest snapshot of each valid game only, validated & deduplicated.
    links_df = pd.DataFrame(links)
    latest = games[["game_id", "source_fetched_at"]]
    links_df = links_df.merge(latest, on=["game_id", "source_fetched_at"], how="inner")
    links_df = links_df.drop(columns="source_fetched_at").drop_duplicates(["game_id", "link_type", "link_id"])
    links_df = pd.DataFrame([GameLink.model_validate(r).model_dump() for r in links_df.to_dict("records")])
    stats.silver_links = len(links_df)

    silver_dir.mkdir(parents=True, exist_ok=True)
    games.to_parquet(silver_dir / "games.parquet", index=False)
    snapshots.to_parquet(silver_dir / "game_snapshots.parquet", index=False)
    links_df.to_parquet(silver_dir / "game_links.parquet", index=False)
    pd.DataFrame(
        rejected, columns=["game_id", "game_name", "snapshot_date", "reason", "raw_record"]
    ).to_parquet(silver_dir / "rejected_records.parquet", index=False)
    (silver_dir / "_transform_stats.json").write_text(json.dumps(asdict(stats), indent=2))
    logger.info("Silver: %s", asdict(stats))
    return stats
