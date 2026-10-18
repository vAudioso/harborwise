# HarborWise

**Arrive when the berth is ready.**

[![tests](https://github.com/vAudioso/harborwise/actions/workflows/tests.yml/badge.svg)](https://github.com/vAudioso/harborwise/actions/workflows/tests.yml)
[![code licence: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![data licence: CC BY-NC-SA 4.0](https://img.shields.io/badge/data-CC%20BY--NC--SA%204.0-lightgrey.svg)](docs/data.md)

Ships often race to port only to wait hours at anchor because their berth is still taken. That burns fuel and money for nothing. HarborWise does three things:

1. **Forecasts when a berth will be free:** a 25% / 50% / 90% chance window, with a confidence label.
2. **Recommends the speed** that gets the ship there just in time, weighing fuel against the ship's time.
3. **Shows it all on a website:** the berth map, the ships alongside, every candidate speed and why one was chosen.

It is trained on a year of real ship-tracking data (AIS) from the Caribbean and Gulf of Mexico, and built for the **IBM Z Datathon**.

## Results at a glance

Built for **scheduled liner ships (container and cruise)**. Tested on November–December 2019, which the models never saw during training.

| Predicting how long a ship stays, at arrival | Average error (MAE) | RMSE |
|---|---:|---:|
| Global median | 8.1 h | 15.8 h |
| Port median | 7.1 h | 14.6 h |
| Random Forest | 5.3 h | 12.6 h |
| HistGradientBoosting | 5.2 h | 12.5 h |
| **GradientBoosting** | **5.2 h** | **12.3 h** |

- **26% more accurate than the port's usual time.** More than half of cruise ships are predicted within 1 hour.
- **In a replay of real berth traffic:** 21% less waiting at anchor, and about **$1,550 saved per arrival**. These savings are simulated, not measured.
- **Other ship types:** tankers, bulk carriers and general cargo ships are supported with separate models, labelled lower confidence.

Full results and limitations: [docs/results.md](docs/results.md).

## Try it

You need Python 3.11+ and Git. On macOS, also run `brew install libomp`.

```bash
git clone https://github.com/vAudioso/harborwise.git
cd harborwise
make quickstart
```

This installs everything, downloads the data and the trained models, and opens the website at **http://localhost:8000/app/**. Next time, `make app` is enough. Run `make help` to see every command.

New to this? Follow the step-by-step guide: [docs/getting-started.md](docs/getting-started.md). It covers Windows, VS Code and common problems.

## What's in this repository

```
harborwise/
├── web/          the website (served at /app/)
├── api/          the server: speed recommendations, results, data quality (FastAPI)
├── harborwise/   the core code: features, models, fuel model, speed optimizer
├── pipeline/     the training steps, from raw data to tested models (make pipeline)
├── scripts/      one-command downloads of the data and trained models
├── tests/        automatic checks: unit tests, leakage tests, API and website contract
├── docs/         guides: getting started, how it works, results, API, data, pitch script
├── reports/      generated reports and charts (test results, simulation, data audit)
├── experiments/  every experiment run, one row each
├── data/         raw and processed data (downloaded, not stored in git)
└── models/       trained models (downloaded, not stored in git)
```

## Documentation

| Guide | For |
|---|---|
| [Getting started](docs/getting-started.md) | Installing and running it, step by step |
| [How it works](docs/how-it-works.md) | The pipeline, the models and the speed optimizer |
| [Results](docs/results.md) | All the numbers, what they mean, and the limitations |
| [API](docs/api.md) | Every endpoint, with examples |
| [Data](docs/data.md) | The dataset, what each record means, and its licence |
| [Pitch script](docs/pitch-script.md) | The 3-minute presentation |
| [Contributing](CONTRIBUTING.md) | How the team works: branches, pull requests, ground rules |

## Team roles

| Role | Area |
|---|---|
| BE1 | Data engineering and validation (`pipeline/phase1/`, `pipeline/build_dataset.py`) |
| BE2 | Features and regression (`harborwise/features.py`, `pipeline/train_regression.py`, `pipeline/train_turnaround.py`) |
| BE3 | Classification, uncertainty and evaluation (`pipeline/train_classification.py`, `train_quantile.py`, `evaluate.py`) |
| BE4 | Fuel model, optimizer, simulation and API (`harborwise/optimizer.py`, `pipeline/simulate.py`, `api/`) |
| FE1, FE2 | Website and charts (`web/`) |

## Data, licence and citation

- **Code:** [MIT licence](LICENSE).
- **Data:** Iphar et al. (2024), *Port calls and vessel trajectory dataset in the Caribbean with accurate port quays survey*, Zenodo [10.5281/zenodo.10380638](https://doi.org/10.5281/zenodo.10380638), licensed **CC BY-NC-SA 4.0** (non-commercial). The processed data and trained models in our [release](https://github.com/vAudioso/harborwise/releases) are derived from it and carry the same licence.
- **To cite HarborWise,** use the "Cite this repository" button on GitHub ([CITATION.cff](CITATION.cff)).
