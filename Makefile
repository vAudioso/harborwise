PY := .venv/bin/python

.PHONY: setup data pipeline quick api test clean
setup:            ## create the virtualenv and install dependencies
	python3 -m venv .venv && $(PY) -m pip install -U pip && $(PY) -m pip install -r requirements.txt
data:             ## Phase 1–2: raw CSVs -> processed tables + checkpoint dataset
	$(PY) -m pipeline.build_dataset && $(PY) -m pipeline.build_features
pipeline:         ## full pipeline: data, E00–E11, models, reports
	$(PY) -m pipeline.run_all
quick:            ## fast smoke run of the full pipeline
	$(PY) -m pipeline.run_all --quick
api:              ## serve the API on http://127.0.0.1:8000 (docs at /docs)
	$(PY) -m uvicorn api.main:app --reload
test:
	$(PY) -m pytest -q
clean:
	rm -rf data/processed/* models/* experiments/* reports/figures logs
