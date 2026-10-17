# port-call-analysis

A data-driven approach to predicting maritime port call durations and optimizing vessel arrival times.

## PortPulse backend

PortPulse predicts when a berth will free up and recommends a speed for an incoming ship, so it spends less time at anchor and burns less fuel. The models train on the 2019 Caribbean AIS dataset (Iphar et al., *Data in Brief* 2024).

This repo covers the whole backend: data validation (BE1), features and regression (BE2), classification, imbalance handling, uncertainty and evaluation (BE3), and the optimizer, simulation and API (BE4). The frontend (FE1/FE2) can go in `web/`.

### Quick start (VS Code)

1. Open this folder in VS Code and accept the recommended extensions. The Python interpreter is already set to `.venv`.
2. If `.venv` doesn't exist yet: **Terminal → Run Task → Setup: create venv + install**, or run `make setup`.
   - macOS only: XGBoost needs OpenMP. Install it with `brew install libomp`.
3. Put the 13 raw CSVs in `data/raw/`. They aren't in the repo because they're too large. Download them from the dataset's Zenodo record ([zenodo.org/records/10380638](https://zenodo.org/records/10380638)). The trained models aren't in the repo either, so run step 4 once after cloning.
4. Build everything with **Run and Debug → "Pipeline: run everything"**, or `make pipeline`. It takes about 15–20 min. `make quick` is a roughly 5-minute smoke run with fewer trees.
5. Serve the API with **Run and Debug → "API: run PortPulse"**, or `make api`. Then open http://127.0.0.1:8000/docs.
6. Run the tests in the Testing panel, or with `make test`.

On a fresh clone, step 4 rebuilds the data and models before step 5 will work.

### Layout

```
data/raw/            13 pipe-delimited CSVs (input, untouched)
data/processed/      visits, checkpoints, berths, ports, port_calls (parquet)
pipeline/            one script per step (python -m pipeline.<step>); run_all.py runs them in order
  phase1/            BE1 audit: data-quality profile + berth reconstruction
portpulse/           library code: config, features, models, fuel, optimizer, clearance service, tracking
api/main.py          FastAPI app
models/              regressor / classifier / quantile .joblib + .json metadata
experiments/         experiments.csv, one row per run (E00–E11)
reports/             Phase 1 audit, leakage check, E10 test report, E11 simulation, figures/
tests/               unit tests, leakage tests, API end-to-end tests
```

### Pipeline steps

| Step | Owner | What it does | Output |
|---|---|---|---|
| `build_dataset` | BE1 | Profiles all CSVs. Rebuilds berth visits by testing stop positions against berth polygons, then merges stays split by gaps under 1 h. Keeps commercial ships with conf ≥ 0.5. | `data/processed/*.parquet`, `reports/phase1/` |
| `build_features` | BE2 | Builds checkpoint rows at 1/3/6/12/24 h alongside, labelled with hours left. Uses leakage-safe congestion and vessel-history features and a purged chronological split. | `checkpoints.parquet`, `reports/leakage_check.md` |
| `train_regression` | BE2 | E00 baselines → E07 tuned XGBoost. | `models/regressor.*` |
| `train_classification` | BE3 | "Clears within 6 h": E08 class balance, then E09 class weights plus six resampling strategies × 3 models, with isotonic calibration and threshold choice. | `models/classifier.*` |
| `train_quantile` | BE3 | P25/P50/P90 clearance window: XGBoost multi-quantile with a conformal shift. | `models/quantile.*` |
| `evaluate` | BE3 | E10, the only use of the test set. Breaks errors down by type, checkpoint and port, tests unseen ports and lists the biggest misses. | `reports/E10_*`, `reports/figures/` |
| `simulate` | BE4 | E11 replay of test-period berth occupancies: service speed vs PortPulse vs oracle. | `reports/E11_*` |

**Split:** train Jan–Aug, validation Sep–Oct, test Nov–Dec. The split is on prediction time, and rows whose label crosses into the next period are dropped. Seed 42.

### Results

These are test-set numbers (Nov–Dec 2019). Validation decided everything; the test set was used once.

| | Result |
|---|---|
| Training data | 51,729 commercial berth visits, 6,218 ships, 832 berths, 159 ports → 212k checkpoint rows |
| **Remaining time, MAE** | **14.84 h** for XGBoost vs 16.56 h for the best baseline (berth median × checkpoint): **10.4% better**. Excluding stays over 7 days: 12.39 h. |
| Unseen ports (31 held out) | Model 18.7 h vs baseline 15.8 h. **The model does not generalise to new ports.** Use it for ports it has seen. |
| **Clears within 6 h** | Random forest with class weights, isotonic-calibrated. PR-AUC 0.64 (positive rate 14.7%), precision 0.54, recall 0.70, ECE 0.007 |
| **Clearance window coverage** | P25 23.7% · P50 47.9% · P90 89.4% (targets 25/50/90) |
| **Speed simulation (E11, SIMULATED)** | Fuel −17%, anchorage wait −15%, berth idle +0.5 h per call. Captures 56% of a perfect forecast's cost saving. |

What the imbalance experiments found (E08–E09): class weighting and random oversampling helped the random forest's F1 a little, while SMOTE and Tomek links brought no gain over plain class weights. Resampling distorts probabilities (see `reports/figures/classification_pr_calibration.png`), which is why the chosen model is recalibrated on untouched validation data. Scaling (E04) makes no measurable difference: Ridge is effectively scale-invariant here and tree models are invariant by construction.

Read these before quoting numbers:
- `reports/phase1/PHASE1_AUDIT.md`: what one record means, and why only commercial ships are used.
- `reports/E11_simulation.md`: the assumptions behind every fuel figure.

#### Honest limitations

- Anchorage waiting time is not in the data (port calls only cover stops within about 600 m of quays). E11 derives waits from predicted vs true clearance. It can't be validated against real waits.
- Fuel figures use the cubic speed law with illustrative engine profiles per vessel type (`portpulse/fuel.py`). Ship time is valued so that service speed is optimal when there's no congestion. Any saving therefore comes from just-in-time arrival, not from generic slow steaming.
- Vessel type is known for only 47% of ships. The unknown-type vessels are excluded from training.
- The model was trained on ships alongside for 1–24 h. Predictions for ships alongside more than 48 h are flagged `elapsed_beyond_training_range`.

### API

Base URL: `http://127.0.0.1:8000`. Interactive docs are at `/docs`.

The API runs in **replay mode**: `as_of` is any 2019 UTC time, the API looks up which commercial ships were alongside then, and it predicts using only what was observable at that moment.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service status |
| GET | `/ports` | Ports with commercial berths (name, country, centroid, visits) |
| GET | `/berths/{port_id}` | Berths with capacity, median stay, centroid and polygon (for the map) |
| GET | `/occupied?as_of=&port_id=` | Berths occupied at a moment. Useful for picking a demo berth. |
| POST | `/predict/clearance` | `{berth_id, as_of}` → P25/P50/P90 hours and timestamps until a slot frees, plus a forecast per occupant |
| POST | `/recommend` | `{berth_id, as_of, vessel_type, distance_nm, speed_min?, speed_max?, fuel_price_usd_per_t?, lambda_usd_per_ship_h?, mu_usd_per_idle_h?}` → recommended speed, ETA, expected wait, fuel and CO₂ vs service speed, all candidate speeds, and a "why" explanation |
| GET | `/vessel-profiles` | Fuel model assumptions per vessel type |
| GET | `/experiments?task=&exp_id=` | Rows from `experiments.csv` (for the model results page) |
| GET | `/experiments/summary` | E10 and E11 summaries |

Example:

```bash
curl -s -X POST localhost:8000/recommend -H 'content-type: application/json' \
  -d '{"berth_id":"284_04","as_of":"2019-11-15T12:00:00","vessel_type":"tank","distance_nm":180}'
```

**Optimizer:** `J(v) = F(v) + λ·E[sailing + waiting time] + μ·E[berth idle before arrival]`.
- The clearance P25/P50/P90 values become a distribution that every candidate speed is scored against.
- When a berth with capacity c has k ≥ c ships alongside, a slot frees when the (k−c+1)-th ship leaves.

### Docker

Build the data and models first, then:

```bash
docker build -t portpulse-api . && docker run -p 8000:8000 portpulse-api
```
