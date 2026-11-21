"""Bronze layer: ingest raw BoardGameGeek XML API2 responses, untouched.

Design principles
-----------------
* **Immutable raw storage** - each HTTP response body is stored verbatim with its
  ingestion metadata (URL, status, timestamp, SHA-256). Nothing is parsed here, so
  Silver can always be rebuilt from Bronze if parsing rules change.
* **Polite client** - a minimum interval between calls, exponential back-off with
  jitter on 429 / 5xx / 202 (BGG "request queued"), and ``Retry-After`` support.
* **Checkpointing** - responses are flushed to Parquet every ``flush_every`` batches,
  so a crash after 40 minutes of ingestion only loses the last few calls.
* **Offline fallback** - ``load_sample`` copies a pre-downloaded Bronze snapshot so the
  whole pipeline runs without network access or API token.
"""

from __future__ import annotations

import hashlib
import logging
import random
import shutil
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import requests

try:  # Use the OS certificate store (corporate proxies / antivirus TLS inspection).
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover - optional dependency
    pass

logger = logging.getLogger(__name__)

BGG_API_ROOT = "https://boardgamegeek.com/xmlapi2"
MAX_IDS_PER_REQUEST = 20  # hard limit enforced by BGG on /thing
RETRYABLE_STATUS = {202, 429, 500, 502, 503, 504}

BRONZE_SCHEMA = pa.schema(
    [
        ("run_id", pa.string()),
        ("batch_no", pa.int32()),
        ("requested_ids", pa.list_(pa.int64())),
        ("source_url", pa.string()),
        ("http_status", pa.int16()),
        ("fetched_at", pa.timestamp("us", tz="UTC")),
        ("payload_sha256", pa.string()),
        ("payload", pa.large_string()),
    ]
)


class BGGApiError(RuntimeError):
    """Raised when the API keeps failing after all retries."""


@dataclass
class RawResponse:
    url: str
    status: int
    text: str
    fetched_at: datetime


class BGGClient:
    """Thin, rate-limited HTTP client for the BGG XML API2."""

    def __init__(
        self,
        token: str | None,
        min_interval_s: float = 2.0,
        max_retries: int = 6,
        backoff_base_s: float = 2.0,
        timeout_s: float = 60.0,
        session: requests.Session | None = None,
    ) -> None:
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.timeout_s = timeout_s
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = "bgg-olap-pipeline/1.0 (portfolio project)"
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self._last_call = 0.0

    def _throttle(self) -> None:
        wait = self.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        if retry_after and retry_after.isdigit():
            return float(retry_after)
        return self.backoff_base_s * (2**attempt) + random.uniform(0, 1)

    def get(self, endpoint: str, params: dict[str, str]) -> RawResponse:
        url = f"{BGG_API_ROOT}/{endpoint}"
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout_s)
            except requests.exceptions.SSLError as exc:  # not transient: fail fast
                raise BGGApiError(f"TLS verification failed for {url}: {exc}") from exc
            except requests.RequestException as exc:
                delay = self._backoff(attempt, None)
                logger.warning("Network error (%s), retry %d in %.1fs", exc, attempt + 1, delay)
                time.sleep(delay)
                continue

            if resp.status_code == 200:
                return RawResponse(resp.url, 200, resp.text, datetime.now(UTC))
            if resp.status_code in (401, 403):
                raise BGGApiError(
                    f"HTTP {resp.status_code}: BGG rejected the request. "
                    "Set BGG_API_TOKEN in .env (register an app on boardgamegeek.com) "
                    "or run offline with `--source sample`."
                )
            if resp.status_code in RETRYABLE_STATUS:
                delay = self._backoff(attempt, resp.headers.get("Retry-After"))
                logger.warning(
                    "HTTP %d on %s, retry %d in %.1fs", resp.status_code, endpoint, attempt + 1, delay
                )
                time.sleep(delay)
                continue
            raise BGGApiError(f"Unexpected HTTP {resp.status_code} for {resp.url}")

        raise BGGApiError(f"Giving up on {url} after {self.max_retries} retries")

    def fetch_things(self, ids: Sequence[int]) -> RawResponse:
        if len(ids) > MAX_IDS_PER_REQUEST:
            raise ValueError(f"BGG accepts at most {MAX_IDS_PER_REQUEST} ids per call")
        params = {"id": ",".join(map(str, ids)), "stats": "1", "type": "boardgame"}
        return self.get("thing", params)

    def fetch_hot_ids(self) -> list[int]:
        import xml.etree.ElementTree as ET

        raw = self.get("hot", {"type": "boardgame"})
        return [int(item.attrib["id"]) for item in ET.fromstring(raw.text).iter("item")]


# --------------------------------------------------------------------------- id sources


def random_ids(n: int, max_id: int = 485_000, seed: int = 42) -> list[int]:
    """Uniform random sample of BGG object ids.

    BGG ids are allocated sequentially, so a uniform draw over the id space is an
    unbiased sample of the catalogue (unlike "top 1000" lists, which only show winners).
    """
    rng = random.Random(seed)
    return sorted(rng.sample(range(1, max_id + 1), n))


def read_ids_file(path: Path) -> list[int]:
    tokens = path.read_text(encoding="utf-8").replace(",", "\n").split()
    return sorted({int(t) for t in tokens if t.strip().isdigit()})


def chunked(ids: Sequence[int], size: int = MAX_IDS_PER_REQUEST) -> Iterator[list[int]]:
    for i in range(0, len(ids), size):
        yield list(ids[i : i + size])


# --------------------------------------------------------------------------- bronze writer


def _write_part(rows: list[dict], out_dir: Path, run_id: str, part: int) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{run_id}_part-{part:04d}.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=BRONZE_SCHEMA), path, compression="zstd")
    return path


def ingest(
    ids: Iterable[int],
    client: BGGClient,
    bronze_dir: Path,
    flush_every: int = 50,
) -> list[Path]:
    """Fetch ``ids`` in batches of 20 and append raw responses to Bronze Parquet files."""
    ids = list(ids)
    now = datetime.now(UTC)
    run_id = now.strftime("run_%Y%m%dT%H%M%SZ")
    out_dir = bronze_dir / f"ingestion_date={now:%Y-%m-%d}"
    batches = list(chunked(ids))
    logger.info("Ingesting %d ids in %d batches -> %s", len(ids), len(batches), out_dir)

    written: list[Path] = []
    buffer: list[dict] = []
    for batch_no, batch in enumerate(batches, start=1):
        raw = client.fetch_things(batch)
        buffer.append(
            {
                "run_id": run_id,
                "batch_no": batch_no,
                "requested_ids": batch,
                "source_url": raw.url,
                "http_status": raw.status,
                "fetched_at": raw.fetched_at,
                "payload_sha256": hashlib.sha256(raw.text.encode("utf-8")).hexdigest(),
                "payload": raw.text,
            }
        )
        if batch_no % 10 == 0 or batch_no == len(batches):
            logger.info("  batch %d/%d", batch_no, len(batches))
        if len(buffer) >= flush_every:
            written.append(_write_part(buffer, out_dir, run_id, len(written) + 1))
            buffer = []
    if buffer:
        written.append(_write_part(buffer, out_dir, run_id, len(written) + 1))
    return written


def load_sample(sample_dir: Path, bronze_dir: Path) -> list[Path]:
    """Offline mode: copy the committed Bronze snapshot into the Bronze zone."""
    files = sorted(sample_dir.glob("bronze/*.parquet"))
    if not files:
        raise FileNotFoundError(f"No sample Bronze files under {sample_dir / 'bronze'}")
    out_dir = bronze_dir / "ingestion_date=sample"
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in files:
        target = out_dir / f.name
        shutil.copy2(f, target)
        copied.append(target)
    logger.info("Loaded %d sample Bronze file(s) into %s", len(copied), out_dir)
    return copied
