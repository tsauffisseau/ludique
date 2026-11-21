"""Smoke test: the Streamlit app renders end-to-end against a freshly built warehouse."""

from pathlib import Path

import pytest

from bgg_pipeline.load import build_warehouse
from bgg_pipeline.transform import transform

from .conftest import SQL_DIR

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


def test_dashboard_renders_without_exception(bronze_dir, tmp_path, pg_dsn, monkeypatch):
    testing = pytest.importorskip("streamlit.testing.v1")
    transform(bronze_dir, tmp_path / "silver")
    build_warehouse(tmp_path / "silver", pg_dsn, SQL_DIR)
    monkeypatch.setenv("BGG_PG_DSN", pg_dsn)

    at = testing.AppTest.from_file(str(APP)).run(timeout=60)

    assert not at.exception, at.exception
    assert [m.label for m in at.metric][:2] == ["Games in catalogue", "With ≥ 30 ratings"]
    assert at.metric[0].value == "3"
