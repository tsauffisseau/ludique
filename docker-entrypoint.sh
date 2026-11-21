#!/bin/sh
# pipeline  : Bronze -> Silver -> Gold (PostgreSQL) -> segmentation -> DQ gate, offline sample
# dashboard : serve Streamlit on :8501 (the warehouse must already be built)
# all       : pipeline, then dashboard (single-container use without compose)
# test      : run the test suite (needs BGG_TEST_PG_DSN)
# anything else is executed as-is (e.g. `python -m bgg_pipeline analysis`)
set -e
case "$1" in
  pipeline)  exec python -m bgg_pipeline run --source sample ;;
  dashboard) exec streamlit run dashboard/app.py --server.address=0.0.0.0 --server.port=8501 ;;
  all)       python -m bgg_pipeline run --source sample
             exec streamlit run dashboard/app.py --server.address=0.0.0.0 --server.port=8501 ;;
  test)      exec python -m pytest ;;
  *)         exec "$@" ;;
esac
