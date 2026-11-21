from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from bgg_pipeline.extract import BRONZE_SCHEMA
from bgg_pipeline.load import SCHEMAS

FIXTURES = Path(__file__).parent / "fixtures"
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
TEST_DSN = os.getenv("BGG_TEST_PG_DSN", "postgresql://bgg:bgg@localhost:55432/bgg_test")


def bronze_row(payload: str, fetched_at: datetime, run_id: str, batch_no: int = 1) -> dict:
    return {
        "run_id": run_id,
        "batch_no": batch_no,
        "requested_ids": [1, 2, 3],
        "source_url": "https://boardgamegeek.com/xmlapi2/thing?id=1,2,3",
        "http_status": 200,
        "fetched_at": fetched_at,
        "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "payload": payload,
    }


def write_bronze(out: Path, payload: str, day: int, run: str) -> None:
    part = out / f"ingestion_date=2026-01-0{day}"
    part.mkdir(parents=True, exist_ok=True)
    row = bronze_row(payload, datetime(2026, 1, day, 6, tzinfo=UTC), run)
    pq.write_table(pa.Table.from_pylist([row], schema=BRONZE_SCHEMA), part / f"{run}.parquet")


@pytest.fixture
def snapshot_1() -> str:
    return (FIXTURES / "thing_snapshot_1.xml").read_text(encoding="utf-8")


@pytest.fixture
def snapshot_2() -> str:
    return (FIXTURES / "thing_snapshot_2.xml").read_text(encoding="utf-8")


@pytest.fixture
def bronze_dir(tmp_path: Path, snapshot_1: str, snapshot_2: str) -> Path:
    """Two ingestion runs one day apart: snapshot_2 re-ingests game 1."""
    out = tmp_path / "bronze"
    write_bronze(out, snapshot_1, 1, "run_a")
    write_bronze(out, snapshot_2, 2, "run_b")
    return out


def _connect_or_create(dsn: str) -> psycopg.Connection:
    """Connect to the test database, creating it on the server if it does not exist yet."""
    try:
        return psycopg.connect(dsn, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        if "does not exist" not in str(exc):
            raise
    params = conninfo_to_dict(dsn)
    dbname = params.pop("dbname")
    with psycopg.connect(make_conninfo(**params, dbname="postgres"), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    return psycopg.connect(dsn, autocommit=True, connect_timeout=3)


@pytest.fixture
def pg_dsn() -> str:
    """A clean PostgreSQL test database (all pipeline schemas dropped). Skips if unreachable."""
    try:
        con = _connect_or_create(TEST_DSN)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL test database unreachable ({TEST_DSN}): {exc}")
    with con:
        for schema in SCHEMAS:
            con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    return TEST_DSN
