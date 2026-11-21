"""Gold layer: load Silver into PostgreSQL and build the star schema from ``sql/``.

A deliberately small, dbt-like runner:

* each SQL model is one file named after the object it creates (``dim_game.sql``);
* every layer lives in its own PostgreSQL schema::

      silver        landing tables, COPY-loaded from data/silver/*.parquet
      staging       stg_*  views (renaming only)
      intermediate  int_*  tables (business rules)
      dw            star schema: dim_*, bridge_*, fact_* (persistent, incremental)
      marts         mart_* views, one per business question (+ clustering outputs)

* dependencies are inferred from the model names referenced in each file and the DAG is
  executed in topological order (dbt's ``ref()`` without the Jinja);
* the whole build runs in **one transaction**: a failing model rolls everything back,
  so the dashboard never reads a half-built warehouse.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import psycopg

logger = logging.getLogger(__name__)

LAYERS = {
    "staging": "staging",
    "intermediate": "intermediate",
    "marts/core": "dw",
    "marts/analytics": "marts",
}
SCHEMAS = ("silver", *LAYERS.values())
# Unqualified names in models resolve through this path (the model's own schema first).
SEARCH_PATH = "dw, intermediate, staging, silver, marts, public"

SILVER_TABLES = {
    "games": "games.parquet",
    "game_snapshots": "game_snapshots.parquet",
    "game_links": "game_links.parquet",
}


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=False)


# --------------------------------------------------------------------------- DAG


def _strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def model_files(sql_dir: Path) -> list[tuple[str, Path]]:
    """Return (layer, path) for every model, in a valid execution order (topological)."""
    models = {
        f.stem: (rank, layer, f)
        for rank, layer in enumerate(LAYERS)
        for f in sorted((sql_dir / layer).glob("*.sql"))
    }
    deps: dict[str, set[str]] = {}
    for name, (rank, layer, path) in models.items():
        body = _strip_comments(path.read_text(encoding="utf-8"))
        refs = {m for m in models if m != name and re.search(rf"\b{m}\b", body)}
        for ref in refs:
            if models[ref][0] > rank:
                raise ValueError(f"{layer}/{name} depends on downstream model {ref}")
        deps[name] = refs

    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in ordered:
            return
        if name in visiting:
            raise ValueError(f"Dependency cycle involving {name}")
        visiting.add(name)
        for ref in sorted(deps[name], key=lambda m: (models[m][0], m)):
            visit(ref)
        visiting.discard(name)
        ordered.append(name)

    for name in sorted(models, key=lambda m: (models[m][0], m)):
        visit(name)
    return [(models[m][1], models[m][2]) for m in ordered]


# --------------------------------------------------------------------------- Silver load


def _py(value):
    """pandas/numpy scalar -> plain Python value psycopg can adapt (NA -> None)."""
    if value is None or isinstance(value, str):
        return value
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") and not hasattr(value, "tzinfo") else value


def _rows(df: pd.DataFrame):
    for rec in df.itertuples(index=False, name=None):
        yield tuple(_py(v) for v in rec)


def load_silver(con: psycopg.Connection, silver_dir: Path, sql_dir: Path) -> dict[str, int]:
    """(Re)create the silver landing tables and bulk-load them with COPY."""
    con.execute((sql_dir / "silver" / "silver_tables.sql").read_text(encoding="utf-8"))
    counts = {}
    for table, filename in SILVER_TABLES.items():
        df = pd.read_parquet(silver_dir / filename)
        cols = [c[0] for c in con.execute(f"SELECT * FROM silver.{table} LIMIT 0").description]
        df = df[cols]
        with con.cursor() as cur, cur.copy(f"COPY silver.{table} ({', '.join(cols)}) FROM STDIN") as copy:
            for row in _rows(df):
                copy.write_row(row)
        counts[table] = len(df)
    logger.info("  silver loaded: %s", counts)
    return counts


# --------------------------------------------------------------------------- build


def build_warehouse(silver_dir: Path, dsn: str, sql_dir: Path, full_refresh: bool = False) -> list[str]:
    built = []
    with connect(dsn) as con:
        if full_refresh:
            logger.warning("  full refresh: dropping the dw schema (history included)")
            con.execute("DROP SCHEMA IF EXISTS dw CASCADE")
        for schema in SCHEMAS:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        load_silver(con, silver_dir, sql_dir)

        for layer, path in model_files(sql_dir):
            con.execute(f"SET LOCAL search_path TO {LAYERS[layer]}, {SEARCH_PATH}")
            try:
                con.execute(path.read_text(encoding="utf-8"))
            except psycopg.Error as exc:
                raise RuntimeError(f"Model {layer}/{path.name} failed: {exc}") from exc
            built.append(path.stem)
            logger.debug("  [%s] %s", layer, path.stem)

        new_rows = con.execute(
            "SELECT COUNT(*) FROM dw.fact_game_snapshot WHERE loaded_at >= transaction_timestamp()"
        ).fetchone()[0]
        total_rows = con.execute("SELECT COUNT(*) FROM dw.fact_game_snapshot").fetchone()[0]
        con.commit()
    logger.info(
        "Gold: %d models built; fact_game_snapshot +%d rows this run (%d in history)",
        len(built),
        new_rows,
        total_rows,
    )
    return built


def query_df(dsn: str, sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Small helper used by the quality checks, the clustering step and the dashboard."""
    with psycopg.connect(dsn) as con, con.cursor() as cur:
        cur.execute(f"SET search_path TO marts, {SEARCH_PATH}")
        cur.execute(sql, params)
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
