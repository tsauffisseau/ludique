from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bgg_pipeline.extract import (
    BRONZE_SCHEMA,
    BGGApiError,
    BGGClient,
    chunked,
    ingest,
    random_ids,
)


class FakeResponse:
    def __init__(self, status: int, text: str = "<items/>", headers: dict | None = None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}
        self.url = "https://boardgamegeek.com/xmlapi2/thing?id=1"


class FakeSession:
    """Replays a scripted list of responses and records the calls."""

    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return self.responses.pop(0)


def fast_client(session: FakeSession) -> BGGClient:
    return BGGClient("token", min_interval_s=0, backoff_base_s=0, session=session)


def test_chunked_respects_api_limit():
    batches = list(chunked(list(range(45))))
    assert [len(b) for b in batches] == [20, 20, 5]


def test_random_ids_are_reproducible_and_unique():
    a, b = random_ids(500, max_id=10_000, seed=1), random_ids(500, max_id=10_000, seed=1)
    assert a == b and len(set(a)) == 500 and min(a) >= 1 and max(a) <= 10_000


def test_token_is_sent_as_bearer():
    session = FakeSession([FakeResponse(200)])
    fast_client(session)
    assert session.headers["Authorization"] == "Bearer token"


def test_client_retries_on_rate_limit_then_succeeds():
    session = FakeSession(
        [
            FakeResponse(429, headers={"Retry-After": "0"}),
            FakeResponse(503),
            FakeResponse(200, "<items>ok</items>"),
        ]
    )
    raw = fast_client(session).fetch_things([1])
    assert raw.status == 200 and raw.text == "<items>ok</items>"
    assert session.calls == 3


def test_client_gives_up_after_max_retries():
    session = FakeSession([FakeResponse(500)] * 10)
    client = BGGClient(None, min_interval_s=0, backoff_base_s=0, max_retries=2, session=session)
    with pytest.raises(BGGApiError):
        client.fetch_things([1])
    assert session.calls == 3


def test_unauthorized_fails_fast_with_actionable_message():
    session = FakeSession([FakeResponse(401)])
    with pytest.raises(BGGApiError, match="BGG_API_TOKEN"):
        fast_client(session).fetch_things([1])
    assert session.calls == 1


def test_too_many_ids_rejected():
    with pytest.raises(ValueError):
        fast_client(FakeSession([])).fetch_things(list(range(21)))


def test_ingest_writes_raw_payloads_to_bronze(tmp_path, snapshot_1):
    session = FakeSession([FakeResponse(200, snapshot_1)] * 3)
    files = ingest(range(1, 46), fast_client(session), tmp_path, flush_every=2)
    assert len(files) == 2  # 3 batches, flushed every 2
    table = pa.concat_tables(pq.ParquetFile(f).read() for f in files)
    assert table.schema.names == BRONZE_SCHEMA.names
    assert table.num_rows == 3
    assert table.column("payload")[0].as_py() == snapshot_1  # stored verbatim
    assert table.column("requested_ids")[2].as_py() == list(range(41, 46))
