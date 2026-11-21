"""Data quality: Silver profiling + Gold SQL tests -> Markdown/JSON report.

Two families of checks, two severities:

* **error** - the data cannot be trusted (duplicate primary key, broken foreign key,
  rating outside [1, 10]...). The pipeline exits with a non-zero code: nothing broken
  reaches the dashboard.
* **warn**  - legitimate but surprising source data (a 60 000-minute wargame,
  min_players > max_players). Kept, counted and shown with examples so an analyst
  can decide; never silently "fixed".
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import psycopg

from .load import SEARCH_PATH

logger = logging.getLogger(__name__)

# Minimum completeness expected per Silver column (fraction of non-null values).
COMPLETENESS_EXPECTATIONS = {
    "game_id": (1.00, "error"),
    "game_name": (1.00, "error"),
    "users_rated": (1.00, "error"),
    "year_published": (0.90, "warn"),
    "min_players": (0.90, "warn"),
    "max_players": (0.90, "warn"),
    "playing_time": (0.75, "warn"),
}


@dataclass
class CheckResult:
    name: str
    layer: str
    severity: str
    description: str
    failing_rows: int
    sample: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.failing_rows == 0

    @property
    def status(self) -> str:
        if self.passed:
            return "PASS"
        return "FAIL" if self.severity == "error" else "WARN"


# --------------------------------------------------------------------------- Silver


def _soft_rules(games: pd.DataFrame, mech_game_ids: set[int]) -> dict[str, tuple[str, pd.Series]]:
    year = pd.Timestamp.now(tz="UTC").year
    return {
        "silver_min_gt_max_players": (
            "min_players > max_players",
            games.min_players > games.max_players,
        ),
        "silver_min_gt_max_playtime": (
            "min_playtime > max_playtime",
            games.min_playtime > games.max_playtime,
        ),
        "silver_playtime_over_24h": ("playing_time > 24 h", games.playing_time > 1440),
        "silver_year_in_future": (f"year_published > {year}", games.year_published > year),
        "silver_year_before_1900": (
            "year_published < 1900 (traditional/ancient games)",
            games.year_published < 1900,
        ),
        "silver_rated_without_weight": (
            ">= 30 ratings but no complexity vote",
            (games.users_rated >= 30) & games.weight_complexity.isna(),
        ),
        "silver_no_mechanic": (
            "game without any mechanic link",
            ~games.game_id.isin(mech_game_ids),
        ),
    }


def profile_silver(silver_dir: Path) -> tuple[dict, list[CheckResult]]:
    games = pd.read_parquet(silver_dir / "games.parquet")
    links = pd.read_parquet(silver_dir / "game_links.parquet")
    rejected = pd.read_parquet(silver_dir / "rejected_records.parquet")
    stats_path = silver_dir / "_transform_stats.json"
    lineage = json.loads(stats_path.read_text()) if stats_path.exists() else {}

    completeness = (games.notna().mean() * 100).round(1).to_dict()
    checks: list[CheckResult] = []

    dup = int(games.game_id.duplicated().sum())
    checks.append(CheckResult("silver_unique_game_id", "silver", "error", "game_id is unique", dup))

    for col, (threshold, severity) in COMPLETENESS_EXPECTATIONS.items():
        ratio = games[col].notna().mean() if len(games) else 0.0
        checks.append(
            CheckResult(
                f"silver_completeness_{col}",
                "silver",
                severity,
                f"{col} filled for >= {threshold:.0%} of games (actual {ratio:.1%})",
                int(games[col].isna().sum()) if ratio < threshold else 0,
            )
        )

    mech_ids = set(links.loc[links.link_type == "mechanic", "game_id"])
    for name, (desc, mask) in _soft_rules(games, mech_ids).items():
        mask = mask.fillna(False).astype(bool)
        sample = games.loc[mask, ["game_id", "game_name", "year_published", "playing_time"]].head(5)
        checks.append(CheckResult(name, "silver", "warn", desc, int(mask.sum()), _records(sample)))

    checks.append(
        CheckResult(
            "silver_quarantine",
            "silver",
            "warn",
            "records rejected by the Pydantic contract (see rejected_records.parquet)",
            len(rejected),
            _records(rejected[["game_id", "game_name", "reason"]].head(5)),
        )
    )

    profile = {
        "lineage": lineage,
        "n_games": len(games),
        "n_links_by_type": links.link_type.value_counts().to_dict(),
        "completeness_pct": completeness,
    }
    return profile, checks


# --------------------------------------------------------------------------- Gold


def _parse_header(sql: str) -> tuple[str, str]:
    severity, description = "error", ""
    for line in sql.splitlines():
        line = line.strip()
        if line.startswith("-- severity:"):
            severity = line.split(":", 1)[1].strip()
        elif line.startswith("-- description:"):
            description = line.split(":", 1)[1].strip()
    return severity, description


def run_sql_tests(dsn: str, tests_dir: Path) -> list[CheckResult]:
    """Each test returns the failing rows; zero rows = pass (dbt-style data tests)."""
    results = []
    with psycopg.connect(dsn) as con, con.cursor() as cur:
        cur.execute(f"SET search_path TO {SEARCH_PATH}")
        for path in sorted(tests_dir.glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            severity, description = _parse_header(sql)
            cur.execute(sql)
            failing = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
            results.append(
                CheckResult(path.stem, "gold", severity, description, len(failing), _records(failing.head(5)))
            )
    return results


# --------------------------------------------------------------------------- report


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def write_report(profile: dict, checks: list[CheckResult], reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    n_fail = sum(c.status == "FAIL" for c in checks)
    n_warn = sum(c.status == "WARN" for c in checks)
    n_pass = sum(c.passed for c in checks)

    lines = [
        "# Data Quality Report",
        "",
        f"_Generated {generated} by `bgg_pipeline.data_quality`._",
        "",
        f"**{n_pass} passed · {n_warn} warnings · {n_fail} failures** "
        f"({'pipeline OK' if n_fail == 0 else 'PIPELINE BLOCKED'})",
        "",
        "## Lineage (Bronze → Silver)",
        "",
        "| Step | Rows |",
        "|---|---:|",
    ]
    labels = {
        "bronze_files": "Bronze Parquet files",
        "bronze_responses": "Raw API responses (HTTP 200)",
        "parsed_records": "Game records parsed from XML",
        "duplicates_removed": "Duplicates removed (one snapshot per game per day)",
        "rejected_records": "Rejected by contract (quarantine)",
        "silver_games": "Games in Silver",
        "silver_snapshots": "Dated metric snapshots in Silver (game × date)",
        "snapshot_dates": "Distinct snapshot dates",
        "silver_links": "Game ↔ taxonomy links in Silver",
    }
    for key, label in labels.items():
        if key in profile["lineage"]:
            lines.append(f"| {label} | {profile['lineage'][key]:,} |")

    lines += [
        "",
        "## Checks",
        "",
        "| Status | Layer | Check | Description | Failing rows |",
        "|---|---|---|---|---:|",
    ]
    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    for c in sorted(checks, key=lambda c: (order[c.status], c.layer, c.name)):
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[c.status]
        lines.append(f"| {icon} {c.status} | {c.layer} | `{c.name}` | {c.description} | {c.failing_rows:,} |")

    lines += ["", "## Completeness of Silver `games`", "", "| Column | % non-null |", "|---|---:|"]
    for col, pct in sorted(profile["completeness_pct"].items(), key=lambda kv: kv[1]):
        lines.append(f"| `{col}` | {pct:.1f} % |")

    examples = [c for c in checks if not c.passed and c.sample]
    if examples:
        lines += ["", "## Examples of flagged rows", ""]
        for c in examples:
            lines += [f"**`{c.name}`** — {c.description}", "", "```json"]
            lines += [json.dumps(row, ensure_ascii=False) for row in c.sample]
            lines += ["```", ""]

    md_path = reports_dir / "data_quality_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (reports_dir / "data_quality_report.json").write_text(
        json.dumps(
            {
                "generated_at": generated,
                "summary": {"passed": n_pass, "warnings": n_warn, "failures": n_fail},
                "profile": profile,
                "checks": [asdict(c) | {"status": c.status} for c in checks],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    logger.info("DQ report: %d pass, %d warn, %d fail -> %s", n_pass, n_warn, n_fail, md_path)
    return md_path


def run_quality(silver_dir: Path, dsn: str, tests_dir: Path, reports_dir: Path) -> list[CheckResult]:
    profile, checks = profile_silver(silver_dir)
    checks += run_sql_tests(dsn, tests_dir)
    write_report(profile, checks, reports_dir)
    return checks
