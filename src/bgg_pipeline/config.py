"""Central configuration: paths, database connection and runtime settings.

Everything can be overridden with environment variables, so the same code runs
locally, in docker-compose and inside the test suite.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# Local default = the docker-compose PostgreSQL published on host port 55432
# (5432 is often taken by a local install). Compose and CI inject their own values.
DEFAULT_PG_DSN = "postgresql://bgg:bgg@localhost:55432/bgg"


def _path(env_var: str, default: Path) -> Path:
    value = os.getenv(env_var)
    return Path(value).resolve() if value else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: _path("BGG_DATA_DIR", PROJECT_ROOT / "data"))
    sample_dir: Path = field(default_factory=lambda: _path("BGG_SAMPLE_DIR", PROJECT_ROOT / "sample_data"))
    sql_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "sql")
    reports_dir: Path = field(default_factory=lambda: _path("BGG_REPORTS_DIR", PROJECT_ROOT / "reports"))

    pg_dsn: str = field(default_factory=lambda: os.getenv("BGG_PG_DSN", DEFAULT_PG_DSN))

    # BGG XML API2 requires a registered application token since 2025.
    api_token: str | None = field(
        default_factory=lambda: os.getenv("BGG_API_TOKEN") or os.getenv("BGG_API_KEY")
    )
    min_request_interval_s: float = field(
        default_factory=lambda: float(os.getenv("BGG_MIN_INTERVAL_S", "2.0"))
    )

    # Optional S3 export (see export.py / sql/athena)
    s3_bucket: str | None = field(default_factory=lambda: os.getenv("BGG_S3_BUCKET"))
    s3_prefix: str = field(default_factory=lambda: os.getenv("BGG_S3_PREFIX", "bgg"))

    @property
    def bronze_dir(self) -> Path:
        return self.data_dir / "bronze" / "bgg_thing"

    @property
    def silver_dir(self) -> Path:
        return self.data_dir / "silver"

    @property
    def gold_export_dir(self) -> Path:
        return self.data_dir / "gold"

    def ensure_dirs(self) -> None:
        for path in (self.bronze_dir, self.silver_dir, self.gold_export_dir, self.reports_dir):
            path.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
