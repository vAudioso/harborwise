# Contributing to HarborWise

Thanks for helping! This guide is written for people new to GitHub.

## The workflow

1. **Get the project** (once): see [docs/getting-started.md](docs/getting-started.md).
2. **Start a branch** for your change, so `main` always works:
   ```bash
   git checkout main
   git pull
   git checkout -b your-name/short-description
   ```
3. **Make your change**, then check that nothing broke:
   ```bash
   make test
   ```
4. **Save and upload it:**
   ```bash
   git add -A
   git commit -m "Say what you changed, in one line"
   git push -u origin your-name/short-description
   ```
5. **Open a pull request.** GitHub prints a link after the push, or go to the repository page and click **Compare & pull request**. Fill in the template.
6. **Ask a teammate to review it.** Merge once it's approved and the automatic tests (the green tick) pass.

## Where things live

| You're working on… | Look in |
|---|---|
| Data cleaning, berth matching (BE1) | `pipeline/phase1/`, `pipeline/build_dataset.py` |
| Features and regression (BE2) | `harborwise/features.py`, `pipeline/train_regression.py`, `pipeline/train_turnaround.py` |
| Classification, uncertainty, evaluation (BE3) | `pipeline/train_classification.py`, `pipeline/train_quantile.py`, `pipeline/evaluate.py` |
| Fuel model, optimizer, simulation, API (BE4) | `harborwise/fuel.py`, `harborwise/optimizer.py`, `pipeline/simulate.py`, `api/` |
| Website (FE1, FE2) | `web/` |
| Documentation | `docs/`, `README.md` |

## Ground rules

- **Never touch the test set (Nov–Dec 2019) while developing.** Choose models on validation data. Only `pipeline/evaluate.py` uses the test set.
- **Features may only use what was known at prediction time.** Add new features to `FEATURE_DOCS` in `harborwise/features.py` with a reason.
- **Fixed random seeds** (`SEED` in `harborwise/config.py`), so results can be reproduced.
- **Label simulated numbers as simulated.** Fuel, CO₂ and money figures come from a simulation, not measurements.
- **Don't commit data or trained models.** They're too large and are ignored automatically. Share them through a GitHub release.
- **Keep the website contract working.** If you change `/recommendations`, `/experiments` or `/data-quality`, run `make test`: `tests/test_contract_v1.py` checks the website will still accept the responses.

## Questions or bugs

[Open an issue](https://github.com/vAudioso/harborwise/issues/new/choose) and pick a template.
