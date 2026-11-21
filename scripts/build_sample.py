"""Rebuild the committed offline snapshot in ``sample_data/bronze/``.

Draws a reproducible uniform random sample of BGG ids, ingests them through the
regular Bronze client, then consolidates the part files into one Parquet file.

    python scripts/build_sample.py --n 15000 --seed 42
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bgg_pipeline.config import get_settings  # noqa: E402
from bgg_pipeline.extract import BGGClient, ingest, random_ids  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=15_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-id", type=int, default=485_000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    client = BGGClient(settings.api_token, min_interval_s=settings.min_request_interval_s)

    with tempfile.TemporaryDirectory() as tmp:
        parts = ingest(random_ids(args.n, args.max_id, args.seed), client, Path(tmp))
        # ParquetFile (not ParquetDataset): no hive partition column added from the path.
        table = pa.concat_tables(pq.ParquetFile(p).read() for p in parts)
        out = settings.sample_dir / "bronze" / "bgg_thing_sample.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, out, compression="zstd", compression_level=19)
    logging.info("Wrote %d raw responses to %s (%.1f MB)", table.num_rows, out, out.stat().st_size / 1e6)


if __name__ == "__main__":
    main()
