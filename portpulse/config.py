"""Project-wide paths, split dates and constants. Every script imports from here."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
MODELS = ROOT / "models"
EXPERIMENTS = ROOT / "experiments"
EXPERIMENTS_CSV = EXPERIMENTS / "experiments.csv"

SEED = 42

# Chronological split on the checkpoint time (all timestamps are UTC, calendar year 2019).
TRAIN_END = "2019-09-01"   # train: Jan–Aug
VAL_END = "2019-11-01"     # validation: Sep–Oct; test: Nov–Dec

# Hours elapsed since berth arrival at which we make a prediction (1/3/6 from the plan, plus
# 12/24 so the API can answer for ships that have been alongside longer).
CHECKPOINTS_H = (1, 3, 6, 12, 24)

# "Clears within N hours" classification target (chosen in Phase 4, see README).
CLEAR_WITHIN_H = 6

COMMERCIAL_TYPES = ("tank", "cont", "bulk", "gcar", "crui")
MIN_CONF = 0.5
MERGE_GAP_H = 1.0

QUANTILES = (0.25, 0.5, 0.9)

for _d in (PROCESSED, MODELS, EXPERIMENTS, REPORTS):
    _d.mkdir(parents=True, exist_ok=True)
