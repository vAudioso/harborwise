PY := .venv/bin/python

.PHONY: setup data pipeline quick api app test clean
setup:            ## create the virtualenv and install dependencies
	python3 -m venv .venv && $(PY) -m pip install -U pip && $(PY) -m pip install -r requirements.txt
data:             ## Phase 1–2: raw CSVs -> processed tables + checkpoint dataset
	$(PY) -m pipeline.build_dataset && $(PY) -m pipeline.build_features
pipeline:         ## full pipeline: data, E00–E11, models, reports
	$(PY) -m pipeline.run_all
quick:            ## fast smoke run of the full pipeline
	$(PY) -m pipeline.run_all --quick
api:              ## serve the API on http://127.0.0.1:8000 (website at /app/, docs at /docs)
	$(PY) -m uvicorn api.main:app --reload
app:              ## serve the API and open the website in your browser
	@echo "Starting HarborWise... the website opens at http://localhost:8000/app/ (Ctrl+C to stop)"
	@(for i in $$(seq 1 60); do curl -s -o /dev/null localhost:8000/health && break; sleep 1; done; open http://localhost:8000/app/) &
	$(PY) -m uvicorn api.main:app
test:
	$(PY) -m pytest -q
clean:
	rm -rf data/processed/* models/* experiments/* reports/figures logs
