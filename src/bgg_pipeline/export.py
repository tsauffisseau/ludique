"""Export the lake to Parquet and (optionally) to Amazon S3 for Athena.

Layout, one folder per table so that Athena external tables can point at it::

    <root>/bronze/bgg_thing/ingestion_date=YYYY-MM-DD/*.parquet   raw API responses
    <root>/silver/<table>/<table>.parquet                         games, game_snapshots, game_links
    <root>/gold/<table>/<table>.parquet                           star schema exported from PostgreSQL

``export_gold`` always runs locally (``data/gold``). ``upload_to_s3`` needs the optional
``boto3`` dependency (``pip install -e ".[aws]"``), AWS credentials in the usual places
(env vars, ~/.aws, instance role) and ``BGG_S3_BUCKET``. The matching Athena DDL lives
in ``sql/athena/``.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from .load import query_df

logger = logging.getLogger(__name__)

GOLD_TABLES = (
    "dw.dim_game",
    "dw.dim_date",
    "dw.dim_year",
    "dw.dim_mechanic",
    "dw.dim_category",
    "dw.dim_designer",
    "dw.dim_publisher",
    "dw.bridge_game_mechanic",
    "dw.bridge_game_category",
    "dw.bridge_game_designer",
    "dw.bridge_game_publisher",
    "dw.fact_game_snapshot",
    "marts.game_clusters",
    "marts.cluster_profiles",
)
SILVER_FILES = ("games", "game_snapshots", "game_links")


def export_gold(dsn: str, out_dir: Path) -> list[Path]:
    written = []
    for qualified in GOLD_TABLES:
        table = qualified.split(".", 1)[1]
        df = query_df(dsn, f"SELECT * FROM {qualified}")
        for col in df.columns:  # NUMERIC -> float, Parquet/Athena friendly
            if df[col].map(lambda v: isinstance(v, Decimal)).any():
                df[col] = df[col].astype(float)
        target = out_dir / table / f"{table}.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(target, index=False)
        written.append(target)
    logger.info("Gold exported: %d tables -> %s", len(written), out_dir)
    return written


def s3_plan(data_dir: Path, prefix: str) -> list[tuple[Path, str]]:
    """(local file, S3 key) pairs, laid out one folder per table for Athena."""
    plan = []
    bronze_root = data_dir / "bronze"
    for f in sorted(bronze_root.rglob("*.parquet")):
        plan.append((f, f"{prefix}/bronze/{f.relative_to(bronze_root).as_posix()}"))
    for name in SILVER_FILES:
        f = data_dir / "silver" / f"{name}.parquet"
        if f.exists():
            plan.append((f, f"{prefix}/silver/{name}/{name}.parquet"))
    gold_root = data_dir / "gold"
    for f in sorted(gold_root.glob("*/*.parquet")):
        plan.append((f, f"{prefix}/gold/{f.relative_to(gold_root).as_posix()}"))
    return plan


def upload_to_s3(data_dir: Path, bucket: str, prefix: str) -> int:
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit('boto3 is required for S3 export: pip install -e ".[aws]"') from exc
    s3 = boto3.client("s3")
    plan = s3_plan(data_dir, prefix.strip("/"))
    for local, key in plan:
        s3.upload_file(str(local), bucket, key)
        logger.info("  s3://%s/%s", bucket, key)
    logger.info("Uploaded %d files to s3://%s/%s", len(plan), bucket, prefix)
    return len(plan)
