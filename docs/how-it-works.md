# How HarborWise works

## The idea in one paragraph

A ship usually sails at full speed to reach port early, then waits at anchor if the berth is still taken. HarborWise forecasts **when the berth will be free**, as a range rather than a single guess. It then picks the **speed** that gets the ship there just in time, weighing fuel against the ship's time and the risk of the berth sitting empty.

```
2019 AIS port calls ──► berth visits ──► features at each moment ──► models ──► speed optimizer ──► API + website
   (data/raw)          (BE1, Phase 1)        (BE2)              (BE2, BE3)        (BE4)          (BE4, FE)
```

## The pipeline

Run it all with `make pipeline` (about 25 minutes). Each step is a script in `pipeline/` and can be run on its own with `python -m pipeline.<step>`.

| Step | Owner | What it does | Output |
|---|---|---|---|
| `build_dataset` | BE1 | Profiles all CSVs. Rebuilds berth visits by testing each ship's stop position against berth polygons, then merges stays split by gaps under 1 h. Keeps commercial ships with confidence ≥ 0.5. | `data/processed/*.parquet`, `reports/phase1/` |
| `build_features` | BE2 | Builds "checkpoint" rows: a ship observed 1, 3, 6, 12 or 24 h after it berthed, labelled with the hours it has left. Features only use what was observable at that moment. | `data/processed/checkpoints.parquet`, `reports/leakage_check.md` |
| `train_turnaround` | BE2 | Predicts the whole stay at arrival: Random Forest, HistGradientBoosting and GradientBoosting vs global and port medians. | `models/turnaround_<segment>.*`, `reports/turnaround_comparison_<segment>.md` |
| `train_regression` | BE2 | Hours left while alongside: experiments E00 (baselines) to E07 (tuned XGBoost). | `models/regressor_<segment>.*` |
| `train_classification` | BE3 | "Will the berth clear within 6 h?": E08 class balance, E09 class weights plus six resampling strategies × 3 models, then calibration and threshold choice. | `models/classifier_<segment>.*` |
| `train_quantile` | BE3 | The clearance window (25%, 50% and 90% chance times): XGBoost multi-quantile regression with a conformal correction. | `models/quantile_<segment>.*` |
| `evaluate` | BE3 | E10, the only time the test set is used: errors by ship type, checkpoint and port, ports never seen in training, the biggest misses. | `reports/E10_*_<segment>.*`, `reports/figures/` |
| `simulate` | BE4 | E11: replays test-period berth traffic and compares sailing at normal speed, HarborWise's speed, and a perfect forecast. | `reports/E11_*_<segment>.*` |

Every run is logged as one row in `experiments/experiments.csv`.

## Two segments

Ships are split into two groups, each with its own models:

- **liner** (container, cruise): fixed schedules, so stays are predictable. This is HarborWise's headline scope.
- **other** (tanker, bulk carrier, general cargo): stays depend on cargo, so forecasts are labelled **lower confidence**.

To run one step for one segment: `HARBORWISE_SEGMENT=other python -m pipeline.train_regression`.

## Keeping it honest

- **Chronological split:** train on January–August 2019, choose models on September–October, test once on November–December. Rows whose answer would leak into the next period are dropped.
- **No peeking at the future:** every feature uses only what was known at prediction time. `tests/test_features.py` recomputes features from data visible at that moment and checks they match. The full list of features and why each is allowed is in `reports/leakage_check.md`.
- **Baselines first:** every model is compared with simple medians (global, port, berth).
- **Calibrated uncertainty:** the 25/50/90% clearance times are checked against what actually happened. On the test set they cover 22/47/89%.

## What the forecast looks at

- how long the ship has already been alongside
- the ship's own earlier stays at this port and berth (liner rotations repeat)
- how busy the port is: ships alongside, recent arrivals and departures
- harbour craft (tugs, pilots) arriving at the berth
- training-period statistics for the berth, port and ship type
- time of day, weekday, month, hurricane season

## The speed optimizer

For every candidate speed v, HarborWise scores:

**J(v) = fuel cost + λ · (sailing time + expected wait) + μ · expected time the berth sits empty before the ship arrives**

- **Fuel** follows the cubic speed law: engine fuel per day rises with the cube of speed. The engine figures per ship type in `harborwise/fuel.py` are illustrative estimates.
- **CO₂** uses the IMO factor of 3.114 t CO₂ per tonne of fuel.
- **λ (the value of the ship's time)** is set so that normal speed is the best choice when there is no queue. Any saving therefore comes from timing the arrival, not from simply sailing slower.
- **μ** is the extra cost of a berth standing idle ($500/h). When a slot is already free, μ is set to 0. The model can't see ships that will arrive in the meantime, so there's no reason to rush.
- **The clearance range** (25/50/90%) becomes a distribution, and every speed is scored against the same samples.
- **Berths with several slots:** a slot frees when enough ships have left.
