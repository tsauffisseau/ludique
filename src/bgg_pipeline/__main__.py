"""Command-line entry point.

python -m bgg_pipeline run                        # full pipeline on the offline sample
python -m bgg_pipeline run --source api --hot     # live: today's 50 trending games
python -m bgg_pipeline refresh                    # weekly: re-snapshot known games, append history
python -m bgg_pipeline extract --source api --random 2000 --seed 7
python -m bgg_pipeline extract --source api --ids 13,822,174430
python -m bgg_pipeline transform | build [--full-refresh] | segment | quality
python -m bgg_pipeline analysis                   # run the commented queries in sql/analysis
python -m bgg_pipeline export [--s3]              # Parquet lake (+ upload for Athena)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .config import Settings, get_settings
from .data_quality import run_quality
from .extract import BGGClient, ingest, load_sample, random_ids, read_ids_file
from .load import build_warehouse, query_df
from .transform import known_game_ids, transform

logger = logging.getLogger("bgg_pipeline")


def step_extract(s: Settings, args: argparse.Namespace) -> None:
    if args.source == "sample":
        load_sample(s.sample_dir, s.bronze_dir)
        return
    client = BGGClient(s.api_token, min_interval_s=s.min_request_interval_s)
    if args.refresh:
        ids = known_game_ids(s.silver_dir)
    elif args.ids:
        ids = sorted({int(x) for x in args.ids.split(",")})
    elif args.ids_file:
        ids = read_ids_file(Path(args.ids_file))
    elif args.random:
        ids = random_ids(args.random, seed=args.seed)
    else:  # --hot (default for the API source)
        ids = client.fetch_hot_ids()
    ingest(ids, client, s.bronze_dir)


def step_transform(s: Settings, _: argparse.Namespace) -> None:
    transform(s.bronze_dir, s.silver_dir)


def step_build(s: Settings, args: argparse.Namespace) -> None:
    build_warehouse(s.silver_dir, s.pg_dsn, s.sql_dir, full_refresh=args.full_refresh)


def step_segment(s: Settings, _: argparse.Namespace) -> None:
    from .clustering import run_segmentation

    run_segmentation(s.pg_dsn)


def step_quality(s: Settings, _: argparse.Namespace) -> None:
    checks = run_quality(s.silver_dir, s.pg_dsn, s.sql_dir / "tests", s.reports_dir)
    failures = [c for c in checks if c.status == "FAIL"]
    for c in failures:
        logger.error("DQ FAIL %s: %s (%d rows)", c.name, c.description, c.failing_rows)
    if failures:
        raise SystemExit(f"{len(failures)} blocking data quality check(s) failed")


def step_analysis(s: Settings, _: argparse.Namespace) -> None:
    import pandas as pd

    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.max_colwidth", 40):
        for path in sorted((s.sql_dir / "analysis").glob("*.sql")):
            title = path.read_text(encoding="utf-8").splitlines()[0].lstrip("- ")
            print(f"\n=== {title}\n")
            print(query_df(s.pg_dsn, path.read_text(encoding="utf-8")).to_string(index=False))


def step_export(s: Settings, args: argparse.Namespace) -> None:
    from .export import export_gold, upload_to_s3

    export_gold(s.pg_dsn, s.gold_export_dir)
    if args.s3:
        if not s.s3_bucket:
            raise SystemExit("Set BGG_S3_BUCKET (and AWS credentials) to upload to S3")
        upload_to_s3(s.data_dir, s.s3_bucket, s.s3_prefix)


STEPS = {
    "extract": [step_extract],
    "transform": [step_transform],
    "build": [step_build],
    "segment": [step_segment],
    "quality": [step_quality],
    "analysis": [step_analysis],
    "export": [step_export],
    "run": [step_extract, step_transform, step_build, step_segment, step_quality],
    "refresh": [step_extract, step_transform, step_build, step_segment, step_quality],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bgg_pipeline", description="BGG OLAP pipeline")
    parser.add_argument("command", choices=STEPS)
    parser.add_argument("--source", choices=["sample", "api"], default="sample")
    ids = parser.add_mutually_exclusive_group()
    ids.add_argument("--hot", action="store_true", help="API: today's hot games (default)")
    ids.add_argument("--ids", help="API: comma-separated BGG ids")
    ids.add_argument("--ids-file", help="API: file with one id per line")
    ids.add_argument("--random", type=int, help="API: uniform random sample of N ids")
    ids.add_argument("--refresh", action="store_true", help="API: re-snapshot the games already known")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--full-refresh", action="store_true", help="build: drop and rebuild the dw schema")
    parser.add_argument("--s3", action="store_true", help="export: also upload the lake to S3")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "refresh":  # weekly incremental snapshot of the known catalogue
        args.source, args.refresh = "api", True
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    settings = get_settings()
    settings.ensure_dirs()
    for step in STEPS[args.command]:
        start = time.perf_counter()
        logger.info("==> %s", step.__name__.removeprefix("step_"))
        step(settings, args)
        logger.info("    done in %.1fs", time.perf_counter() - start)


if __name__ == "__main__":
    sys.exit(main())
