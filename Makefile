PYTHON ?= python
export PYTHONPATH := src

.DEFAULT_GOAL := help
.PHONY: help up down install db run-pipeline refresh extract transform build segment quality analysis \
        export export-s3 test lint dashboard synthetic-sample clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---- Docker (recommended) ----------------------------------------------------------
up: ## docker compose up: PostgreSQL + pipeline + dashboard on http://localhost:8501
	docker compose up --build

down: ## Stop the stack (add -v to also drop the database volume)
	docker compose down

# ---- Local Python ------------------------------------------------------------------
install: ## Install dependencies (runtime + dashboard + dev)
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e . --no-deps

db: ## Start only PostgreSQL (for local runs), on localhost:55432
	docker compose up -d postgres

run-pipeline: ## Full pipeline on the offline sample: Bronze -> Silver -> Gold -> segments -> DQ gate
	$(PYTHON) -m bgg_pipeline run --source sample

refresh: ## Weekly incremental snapshot from the live API (needs BGG_API_TOKEN)
	$(PYTHON) -m bgg_pipeline refresh

extract: ## Bronze only (offline sample)
	$(PYTHON) -m bgg_pipeline extract --source sample

transform: ## Silver only
	$(PYTHON) -m bgg_pipeline transform

build: ## Gold star schema only (incremental)
	$(PYTHON) -m bgg_pipeline build

segment: ## K-means segmentation
	$(PYTHON) -m bgg_pipeline segment

quality: ## Data-quality checks + report (fails on blocking issues)
	$(PYTHON) -m bgg_pipeline quality

analysis: ## Run the commented SQL queries of sql/analysis
	$(PYTHON) -m bgg_pipeline analysis

export: ## Export the lake to Parquet (data/gold)
	$(PYTHON) -m bgg_pipeline export

export-s3: ## Export + upload to S3 for Athena (needs BGG_S3_BUCKET, AWS credentials, boto3)
	$(PYTHON) -m bgg_pipeline export --s3

test: ## Unit + end-to-end tests (needs PostgreSQL: `make db`)
	$(PYTHON) -m pytest

lint: ## Static checks
	$(PYTHON) -m ruff check src tests scripts dashboard
	$(PYTHON) -m ruff format --check src tests scripts dashboard

dashboard: ## Launch the Streamlit dashboard on http://localhost:8501
	$(PYTHON) -m streamlit run dashboard/app.py

synthetic-sample: ## Regenerate the synthetic offline sample
	$(PYTHON) scripts/generate_synthetic_sample.py

clean: ## Remove generated data and caches
	rm -rf data .pytest_cache .ruff_cache
