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

# ---- Segments ------------------------------------------------------------------------------
# HarborWise is scoped to scheduled liner ships (container, cruise): they repeat ports and
# berths on fixed rotations, so their stays are predictable. Tankers, bulk carriers and general
# cargo get their own, lower-confidence models. Each ship type belongs to exactly one segment.
import os  # noqa: E402

SEGMENTS = {"liner": ("cont", "crui"), "other": ("tank", "bulk", "gcar")}
SEGMENT_OF = {t: s for s, types in SEGMENTS.items() for t in types}
SEGMENT_CONFIDENCE = {"liner": "high", "other": "lower"}
_ACTIVE = {"segment": os.environ.get("HARBORWISE_SEGMENT", "liner")}


def set_segment(name: str):
    if name not in SEGMENTS:
        raise ValueError(f"unknown segment {name!r}; expected one of {list(SEGMENTS)}")
    _ACTIVE["segment"] = name


def active_segment() -> str:
    return _ACTIVE["segment"]


def seg_path(folder, filename: str, segment: str | None = None):
    """models/regressor.joblib -> models/regressor_liner.joblib (active segment by default)."""
    stem, dot, ext = filename.rpartition(".")
    return folder / f"{stem}_{segment or active_segment()}.{ext}"
