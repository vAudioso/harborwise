"""Experiment log: every run appends one row to experiments/experiments.csv."""
import json
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss, f1_score, mean_absolute_error,
                             mean_squared_error, median_absolute_error, precision_score, recall_score)

from harborwise.config import EXPERIMENTS_CSV, SEED, TRAIN_END, VAL_END, active_segment


def regression_metrics(y, pred) -> dict:
    return {"mae": float(mean_absolute_error(y, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y, pred))),
            "medae": float(median_absolute_error(y, pred))}


def expected_calibration_error(y, p, bins: int = 10) -> float:
    y, p = np.asarray(y), np.asarray(p)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    ece = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            ece += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(ece)


def classification_metrics(y, proba, threshold: float = 0.5) -> dict:
    pred = (proba >= threshold).astype(int)
    tn = int(((pred == 0) & (y == 0)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum()); tp = int(((pred == 1) & (y == 1)).sum())
    return {"precision": float(precision_score(y, pred, zero_division=0)),
            "recall": float(recall_score(y, pred, zero_division=0)),
            "f1": float(f1_score(y, pred, zero_division=0)),
            "pr_auc": float(average_precision_score(y, proba)),
            "brier": float(brier_score_loss(y, proba)),
            "ece": expected_calibration_error(y, proba),
            "threshold": float(threshold), "tn": tn, "fp": fp, "fn": fn, "tp": tp}


def log_run(exp_id: str, task: str, model: str, metrics: dict, config: dict | None = None,
            features: list | None = None, n_train: int | None = None, n_eval: int | None = None,
            eval_split: str = "val", train_seconds: float | None = None, notes: str = "") -> dict:
    row = {"exp_id": exp_id, "segment": active_segment(), "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "task": task, "model": model, "eval_split": eval_split,
           "train_end": TRAIN_END, "val_end": VAL_END, "seed": SEED,
           "n_train": n_train, "n_eval": n_eval,
           "train_seconds": None if train_seconds is None else round(train_seconds, 2),
           **{k: (round(v, 5) if isinstance(v, float) else v) for k, v in metrics.items()},
           "config": json.dumps(config or {}, default=str), "features": json.dumps(features or []), "notes": notes}
    df = pd.DataFrame([row])
    if EXPERIMENTS_CSV.exists():
        df = pd.concat([pd.read_csv(EXPERIMENTS_CSV), df], ignore_index=True)
    df.to_csv(EXPERIMENTS_CSV, index=False)
    shown = {k: row[k] for k in metrics if k in ("mae", "rmse", "medae", "pr_auc", "f1", "recall", "precision", "coverage")}
    print(f"[{exp_id} {active_segment()}] {task:<14} {model:<38} {shown}", flush=True)
    return row


def reset_experiments(prefixes: tuple[str, ...]):  # exact experiment IDs, e.g. ("E08", "E09")
    """Drop earlier rows for these experiment IDs so a rerun replaces them instead of duplicating."""
    if EXPERIMENTS_CSV.exists():
        df = pd.read_csv(EXPERIMENTS_CSV)
        seg = df["segment"] if "segment" in df else pd.Series("", index=df.index)
        df = df[~(df["exp_id"].astype(str).isin(prefixes) & ((seg == active_segment()) | seg.isna()))]
        df.to_csv(EXPERIMENTS_CSV, index=False)


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self.t0
