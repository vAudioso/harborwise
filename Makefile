PY := .venv/bin/python
OPEN := $(shell command -v open || command -v xdg-open || echo echo)

.DEFAULT_GOAL := help
.PHONY: help setup quickstart download-data download-models data pipeline quick api app test clean

help:             ## list the commands
	@echo "HarborWise commands (run them from this folder):"
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-16s %s\n", $$1, $$2}'

setup:            ## create the Python environment and install everything (once)
	python3 -m venv .venv && $(PY) -m pip install -U pip && $(PY) -m pip install -r requirements.txt

quickstart:       ## first run: setup + download data and trained models + open the website
	$(MAKE) setup download-data download-models app

download-data:    ## download the 2019 AIS dataset from Zenodo into data/raw/ (67 MB)
	python3 scripts/download_data.py

download-models:  ## download the trained models (140 MB) instead of training them yourself
	python3 scripts/download_models.py

data:             ## rebuild the processed tables and checkpoint dataset from data/raw/
	$(PY) -m pipeline.build_dataset && $(PY) -m pipeline.build_features

pipeline:         ## retrain everything from data/raw/: models, experiments, reports (~25 min)
	$(PY) -m pipeline.run_all

quick:            ## fast smoke run of the whole pipeline (~5 min, fewer trees)
	$(PY) -m pipeline.run_all --quick

api:              ## start the server with auto-reload (website /app/, docs /docs)
	$(PY) -m uvicorn api.main:app --reload

app:              ## start the server and open the website in your browser
	@echo "Starting HarborWise... the website opens at http://localhost:8000/app/ (Ctrl+C to stop)"
	@(for i in $$(seq 1 60); do curl -s -o /dev/null localhost:8000/health && break; sleep 1; done; $(OPEN) http://localhost:8000/app/) &
	$(PY) -m uvicorn api.main:app

test:             ## run the tests
	$(PY) -m pytest -q

clean:            ## delete generated models, processed data, figures and logs (keeps raw data and code)
	rm -f models/*.joblib data/processed/*.parquet reports/figures/*.png reports/phase1/*.parquet
	rm -rf logs .pytest_cache
