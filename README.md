# HarborWise

HarborWise predicts when a berth will free up and recommends a speed for an incoming ship, so it spends less time at anchor and burns less fuel. The models train on the 2019 Caribbean AIS dataset (Iphar et al., *Data in Brief* 2024).

**Scope:** HarborWise is built for **scheduled liner ships (container and cruise)**. They repeat ports and berths on fixed rotations, so their stays are predictable. Tankers, bulk carriers and general cargo ships get their own models, labelled **lower confidence** in the API.

## Backend

This repo holds the whole project: data validation (BE1), features and regression (BE2), classification, imbalance handling, uncertainty and evaluation (BE3), the optimizer, simulation and API (BE4), and the website (FE1/FE2) in `web/`, served by the API at **http://127.0.0.1:8000/app/**.

### Quick start (VS Code)

1. Open this folder in VS Code and accept the recommended extensions. The Python interpreter is already set to `.venv`.
2. If `.venv` doesn't exist yet: **Terminal → Run Task → Setup: create venv + install**, or run `make setup`.
   - macOS only: XGBoost needs OpenMP. Install it with `brew install libomp`.
3. Put the 13 raw CSVs in `data/raw/`. They aren't in the repo because they're too large. Download them from the dataset's Zenodo record ([zenodo.org/records/10380638](https://zenodo.org/records/10380638)). The trained models aren't in the repo either, so run step 4 once after cloning.
4. Build everything with **Run and Debug → "Pipeline: run everything"**, or `make pipeline`. It takes about 15–20 min. `make quick` is a roughly 5-minute smoke run with fewer trees.
5. Serve the API with **Run and Debug → "API: run HarborWise"**, or `make api`. Then open:
   - **http://127.0.0.1:8000/app/**: the website, connected to the live API (badge "LIVE · HARBORWISE API")
   - http://127.0.0.1:8000/app/classic.html: the earlier website build
   - http://127.0.0.1:8000/docs: interactive API docs
6. Run the tests in the Testing panel, or with `make test`.

On a fresh clone, step 4 rebuilds the data and models before step 5 will work.

### Layout

```
data/raw/            13 pipe-delimited CSVs (input, untouched)
data/processed/      visits, checkpoints, berths, ports, port_calls (parquet)
pipeline/            one script per step (python -m pipeline.<step>); run_all.py runs them in order
  phase1/            BE1 audit: data-quality profile + berth reconstruction
harborwise/           library code: config, features, models, fuel, optimizer, clearance service, tracking
api/main.py          FastAPI app; api/contract_v1.py: the website contract (/recommendations, /experiments, /data-quality)
web/                 the website: index.html (current build), classic.html (earlier build), served at /app/
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
| `train_turnaround` | BE2 | Turnaround time predicted at arrival: Random Forest, HistGradientBoosting and GradientBoosting vs global and port medians. | `models/turnaround_<segment>.*`, `reports/turnaround_comparison_<segment>.md` |
| `train_regression` | BE2 | E00 baselines → E07 tuned XGBoost. | `models/regressor_<segment>.*` |
| `train_classification` | BE3 | "Clears within 6 h": E08 class balance, then E09 class weights plus six resampling strategies × 3 models, with isotonic calibration and threshold choice. | `models/classifier_<segment>.*` |
| `train_quantile` | BE3 | P25/P50/P90 clearance window: XGBoost multi-quantile with a conformal shift. | `models/quantile_<segment>.*` |
| `evaluate` | BE3 | E10, the only use of the test set. Breaks errors down by type, checkpoint and port, tests unseen ports and lists the biggest misses. | `reports/E10_*_<segment>.*`, `reports/figures/` |
| `simulate` | BE4 | E11 replay of test-period berth occupancies: service speed vs HarborWise vs oracle. | `reports/E11_*_<segment>.*` |

**Segments:** every step from `train_turnaround` on runs twice: once for `liner` (container, cruise) and once for `other` (tanker, bulk, general cargo). Each ship is scored by its own segment's models. To run one step for one segment: `HARBORWISE_SEGMENT=other python -m pipeline.train_regression`.

**Split:** train Jan–Aug, validation Sep–Oct, test Nov–Dec. The split is on prediction time, and rows whose label crosses into the next period are dropped. Seed 42.

### Results

These are test-set numbers (Nov–Dec 2019). Validation decided everything; the test set was used once.

#### Headline: liner ships (container and cruise)

**Turnaround time predicted at arrival** (3,886 test visits, median stay 12.8 h):

| Model | MAE (h) | RMSE (h) | Within 1 h |
|---|---:|---:|---:|
| Global median | 8.13 | 15.79 | 9.5% |
| Port median | 7.06 | 14.59 | 21.2% |
| Random Forest | 5.31 | 12.63 | 26.5% |
| HistGradientBoosting | 5.21 | 12.48 | 29.0% |
| **GradientBoosting** | **5.20** | **12.33** | 28.4% |

GradientBoosting is 26% more accurate than the port median and 36% more accurate than the global median. Its median error is 2.5 h. Cruise ships, which run fixed timetables, have a median error of 0.8 h, and 56% are within 1 h. Container ships have a median error of 3.4 h.

| Other liner results | |
|---|---|
| Remaining time while alongside (MAE) | **5.60 h** (RMSE 13.2) vs 6.90 h for the berth median and 7.30 h for the port median |
| Ports held out of training (16) | Model 12.4 h vs baseline 15.4 h: it does generalise to new ports for liner ships |
| "Clears within 6 h" | Random forest with SMOTE + Tomek links, isotonic-calibrated: precision 0.65, recall 0.76, PR-AUC 0.75 (positive rate 25%) |
| Clearance window coverage | P25 22% · P50 47% · P90 89% (targets 25/50/90) |
| **Speed simulation (SIMULATED)** | Anchorage wait −21%, fuel −6.6% (2.9 t per arrival), about **$1,550 net saved per arrival**. Captures 51% of a perfect forecast's saving. |

#### Lower confidence: tankers, bulk carriers, general cargo

These ships stay longer (median 35 h) and less predictably.

| Turnaround at arrival | MAE (h) | RMSE (h) |
|---|---:|---:|
| Global median | 25.67 | 44.76 |
| Port median | 23.35 | 42.99 |
| **Random Forest** | **18.91** | **38.56** |
| HistGradientBoosting | 19.02 | 38.41 |
| GradientBoosting | 19.01 | 38.29 |

- **Remaining time:** 19.6 h MAE, against 21.5 h for the berth median.
- **"Clears within 6 h":** PR-AUC 0.49.
- **Clearance window:** coverage is on target, at 25/50/90%.
- **Speed simulation:** fuel −30%, wait −14%, about $2,490 net saved per arrival.

The savings are larger than for liners because these ships wait longer, but the forecasts behind them are less reliable.

**Why not under 1 hour of error?** Departure depends on cargo volumes, crane and labour plans and schedules, and none of these are in the data. Liner ships get close because their schedules repeat.

**Imbalance experiments (E08–E09):**
- **Liner ships:** for the random forest, every resampling strategy scored within 0.003 PR-AUC of the others. SMOTE + Tomek links came out marginally best.
- **Other ships:** no resampling at all was best.
- **Probabilities:** resampling distorts them, so the chosen classifier is recalibrated on untouched validation data.
- **Scaling (E04):** no measurable difference.

Read these before quoting numbers:
- `reports/phase1/PHASE1_AUDIT.md`: what one record means, and why only commercial ships are used.
- `reports/E11_simulation_liner.md`: the assumptions behind every fuel figure.
- `reports/pitch_script.md`: the 3-minute pitch script.

#### Honest limitations

- Anchorage waiting time is not in the data (port calls only cover stops within about 600 m of quays). E11 derives waits from predicted vs true clearance. It can't be validated against real waits.
- Fuel figures use the cubic speed law with illustrative engine profiles per vessel type (`harborwise/fuel.py`). Ship time is valued so that service speed is optimal when there's no congestion. Any saving therefore comes from just-in-time arrival, not from generic slow steaming.
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
| GET | `/experiments/runs?task=&exp_id=&segment=` | Every logged run from `experiments.csv` |
| GET | `/experiments/summary` | E10, E11 and turnaround summaries per segment |

**Website contract v1.0** (`api/contract_v1.py`, tested in `tests/test_contract_v1.py`). The website calls these:

| Method | Path | Purpose |
|---|---|---|
| POST | `/recommendations` | One voyage: `{vessel_type, daily_fuel_t, destination_port_id, distance_nm, baseline_speed_kn, speed_range, arrival_flexibility_h, max_late_risk, fuel_price_usd_t, planning_time_utc}` → destination berth (with polygon), P25/P50/P90 clearance, every candidate speed with late risk and feasibility, the recommended speed, baseline, explanation and timing |
| GET | `/experiments` | Test-set results for the Model Results page (liner segment) |
| GET | `/data-quality` | Dataset audit and EDA counts |
| GET | `/figures/{name}.png` | Report figures |
| GET | `/app/` | The website |

How `/recommendations` picks the destination berth:
1. a full berth used mainly by this ship type
2. a full berth of the ship's segment
3. the most occupied berth of this type
4. the busiest berth

Late risk is the chance the berth stands free for longer than the arrival flexibility before the ship arrives. When the chosen berth has a free slot, there's no queue to time against, so the ship keeps its normal speed (no idle-berth penalty).

**Demo ports:** the website's ports Cartagena, Kingston and San Juan have no ship positions in the 2019 data, so the API uses the nearest port with berth data and says so in every response:
- Cartagena → Mamonal, in the same bay
- Kingston → Port Esquivel
- San Juan → St Thomas

Ports outside the Caribbean and Gulf of Mexico (in the earlier website build) return a clear 404.

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
docker build -t harborwise-api . && docker run -p 8000:8000 harborwise-api
```
