"""Step 5 (BE3): clearance window — P25 / P50 / P90 hours until the berth clears.

XGBoost multi-quantile regression on log1p(hours), reusing the tuned regression depth/
regularisation, then a split-conformal shift per quantile from validation so the stated
coverage holds out of sample. Test coverage is checked in E10.

Usage: python -m pipeline.train_quantile
"""
import json

import joblib
import numpy as np
from xgboost import XGBRegressor

from harborwise.config import MODELS, QUANTILES, SEED, seg_path
from harborwise.data import load_checkpoints, split_xy
from harborwise.models import ClearanceQuantileModel, make_prep
from harborwise.tracking import Timer, log_run, reset_experiments


def quantile_metrics(y, Q, quantiles=QUANTILES) -> dict:
    m = {}
    for i, q in enumerate(quantiles):
        tag = f"p{int(q * 100)}"
        m[f"coverage_{tag}"] = float(np.mean(y <= Q[:, i]))
        diff = y - Q[:, i]
        m[f"pinball_{tag}"] = float(np.mean(np.maximum(q * diff, (q - 1) * diff)))
    lo, hi = Q[:, 0], Q[:, -1]
    m[f"interval_p{int(quantiles[0]*100)}_p{int(quantiles[-1]*100)}_coverage"] = float(np.mean((y >= lo) & (y <= hi)))
    m["interval_median_width_h"] = float(np.median(hi - lo))
    m["coverage"] = m[f"coverage_p{int(quantiles[-1]*100)}"]
    return m


def main():
    reset_experiments(("E09Q",))
    cp = load_checkpoints()
    Xtr, ytr = split_xy(cp, "train")
    Xva, yva = split_xy(cp, "val")
    reg_meta = json.loads((seg_path(MODELS, "regressor.json")).read_text())
    if reg_meta.get("dropped_gt_7d_from_train"):
        keep = ~Xtr["flag_gt_7d"].to_numpy()
        Xtr, ytr = Xtr[keep], ytr[keep]
    p = reg_meta.get("xgb_best_params") or {}
    tuned = {k: p[k] for k in ("max_depth", "min_child_weight", "subsample", "colsample_bytree", "reg_alpha", "reg_lambda") if k in p}

    model = XGBRegressor(objective="reg:quantileerror", quantile_alpha=np.array(QUANTILES), n_estimators=3000,
                         learning_rate=0.05, tree_method="hist", early_stopping_rounds=100, random_state=SEED, n_jobs=-1,
                         **tuned)
    qm = ClearanceQuantileModel(make_prep(), model)
    with Timer() as tm:
        qm.fit(Xtr, ytr, Xva, yva)
    raw = quantile_metrics(yva, np.clip(np.expm1(np.sort(qm._raw(Xva), axis=1)), 0, None))
    log_run("E09Q", "quantile", "XGBoost quantile (uncalibrated)", raw, {"quantiles": QUANTILES, **tuned}, list(qm.prep[-1].get_feature_names_out()),
            len(Xtr), len(Xva), train_seconds=tm.seconds)
    qm.calibrate(Xva, yva)
    cal = quantile_metrics(yva, qm.predict(Xva))
    log_run("E09Q", "quantile", "XGBoost quantile + conformal shift", cal, {"shift_log_space": qm.shift_.round(4).tolist()},
            None, len(Xtr), len(Xva), notes="shift fitted on validation, so validation coverage is by construction; see E10")
    joblib.dump(qm, seg_path(MODELS, "quantile.joblib"))
    (seg_path(MODELS, "quantile.json")).write_text(json.dumps({"quantiles": QUANTILES, "tuned_params": tuned,
                                                      "conformal_shift_log_space": qm.shift_.tolist(),
                                                      "val_uncalibrated": raw, "val_calibrated": cal}, indent=2))


if __name__ == "__main__":
    main()
