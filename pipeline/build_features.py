"""Step 2 (BE2): build the checkpoint dataset and the leakage report.

Usage: python -m pipeline.build_features
"""
import json

import pandas as pd

from harborwise.config import CLEAR_WITHIN_H, PROCESSED, REPORTS, TRAIN_END, VAL_END
from harborwise.data import load_port_calls, load_service_stops, load_visits
from harborwise.features import FEATURE_DOCS, build_checkpoints


def main():
    visits, port_calls = load_visits(), load_port_calls()
    cp = build_checkpoints(visits, port_calls, service_stops=load_service_stops())
    cp.to_parquet(PROCESSED / "checkpoints.parquet", index=False)

    counts = cp["split"].value_counts().to_dict()
    pos = (cp["remaining_h"] <= CLEAR_WITHIN_H).groupby(cp["split"]).mean().round(4).to_dict()
    by_cp = cp[cp["split"] == "train"].groupby("elapsed_h")["remaining_h"].agg(["size", "median"]).round(2)
    summary = {"rows": len(cp), "rows_by_split": counts, "split_dates": {"train_end": TRAIN_END, "val_end": VAL_END},
               f"share_clearing_within_{CLEAR_WITHIN_H}h_by_split": pos,
               "train_rows_and_median_remaining_by_checkpoint": by_cp.to_dict(orient="index")}
    (PROCESSED / "checkpoints_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    lines = ["# Leakage check: is every feature known at prediction time?", "",
             "Prediction time t = arrival + elapsed hours. The label is departure − t.", "",
             "| Feature | Why it is available at t |", "|---|---|"]
    lines += [f"| `{k}` | {v} |" for k, v in FEATURE_DOCS.items()]
    lines += ["", "Excluded on purpose: `duration`, `ts_end`, `n_calls`, `confidence_min` (computed from the whole stay), "
              "`mmsi`, berth and port IDs as numbers (identifiers are only used to look up training-period medians).",
              "", "Tests: `tests/test_features.py` recomputes congestion features using only data visible at t and "
              "checks they match."]
    (REPORTS / "leakage_check.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
