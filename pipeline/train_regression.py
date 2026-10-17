"""Step 3 (BE2): remaining-time regression, experiments E00–E07.

Every run trains on Jan–Aug and is scored on Sep–Oct (validation). The test set (Nov–Dec)
is not touched here; it is used once, in pipeline.evaluate (E10).

Usage: python -m pipeline.train_regression [--quick]
"""
import argparse
import json

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler
from xgboost import XGBRegressor

from portpulse.config import MODELS, SEED
from portpulse.data import load_checkpoints, split_xy
from portpulse.models import MedianBaseline, RemainingTimeModel, make_prep
from portpulse.tracking import Timer, log_run, regression_metrics, reset_experiments


FITTED = {}


def run(exp_id, name, model_obj, Xtr, ytr, Xva, yva, config=None, notes="", log=True):
    with Timer() as tm:
        model_obj.fit(Xtr, ytr, Xva, yva) if isinstance(model_obj, RemainingTimeModel) else model_obj.fit(Xtr, ytr)
    m = regression_metrics(yva, model_obj.predict(Xva))
    feats = model_obj.feature_names if isinstance(model_obj, RemainingTimeModel) else []
    if log:
        log_run(exp_id, "regression", name, m, config, feats, len(Xtr), len(Xva), train_seconds=tm.seconds, notes=notes)
    if isinstance(model_obj, RemainingTimeModel):
        FITTED[name] = (m["mae"], model_obj)
    return m


def hgb(loss="squared_error"):
    return HistGradientBoostingRegressor(loss=loss, max_iter=500, learning_rate=0.05, max_leaf_nodes=63,
                                         min_samples_leaf=40, l2_regularization=1.0, early_stopping=True,
                                         validation_fraction=0.1, random_state=SEED)


def xgb(**kw):
    params = dict(n_estimators=3000, learning_rate=0.05, max_depth=6, min_child_weight=5, subsample=0.8,
                  colsample_bytree=0.8, reg_alpha=0.0, reg_lambda=1.0, tree_method="hist",
                  early_stopping_rounds=100, random_state=SEED, n_jobs=-1)
    params.update(kw)
    return XGBRegressor(**params)


def main(quick: bool = False):
    reset_experiments(("E00", "E01", "E02", "E03", "E04", "E05", "E06", "E07"))
    cp = load_checkpoints()
    Xtr, ytr = split_xy(cp, "train")
    Xva, yva = split_xy(cp, "val")
    results = {}

    # E00 — baselines
    for level in ("global", "port", "berth"):
        results[f"E00_{level}"] = run("E00", f"median baseline ({level} x checkpoint)", MedianBaseline(level), Xtr, ytr, Xva, yva,
                                      {"level": level})

    # E01 — cleaning rule: do >7-day stays (likely lay-ups) help or hurt training?
    keep = ~Xtr["flag_gt_7d"].to_numpy()
    results["E01_all"] = run("E01", "HistGB, train incl. >7d stays", RemainingTimeModel(make_prep(), hgb(), False),
                             Xtr, ytr, Xva, yva, {"train_rows": int(len(Xtr))})
    results["E01_no7d"] = run("E01", "HistGB, train excl. >7d stays", RemainingTimeModel(make_prep(), hgb(), False),
                              Xtr[keep], ytr[keep], Xva, yva, {"train_rows": int(keep.sum())},
                              notes="validation set unchanged (still includes long stays)")
    drop_long = results["E01_no7d"]["mae"] < results["E01_all"]["mae"]
    if drop_long:
        Xtr, ytr = Xtr[keep], ytr[keep]

    # E02 — feature engineering
    results["E02_basic"] = run("E02", "HistGB, basic features", RemainingTimeModel(make_prep("basic"), hgb(), False), Xtr, ytr, Xva, yva,
                               {"feature_set": "basic"})
    results["E02_full"] = run("E02", "HistGB, full features", RemainingTimeModel(make_prep("full"), hgb(), False), Xtr, ytr, Xva, yva,
                              {"feature_set": "full"})

    # E03 — target transform and robust loss
    results["E03_log"] = run("E03", "HistGB, log1p target", RemainingTimeModel(make_prep(), hgb(), True), Xtr, ytr, Xva, yva,
                             {"target": "log1p"})
    results["E03_abs"] = run("E03", "HistGB, raw target, absolute loss", RemainingTimeModel(make_prep(), hgb("absolute_error"), False),
                             Xtr, ytr, Xva, yva, {"target": "raw", "loss": "absolute_error"})
    # Squared-error models (Ridge, forests) use log1p if it beats the raw target; XGBoost also tries
    # the absolute-error objective in E06 because it can optimise MAE directly.
    use_log = results["E03_log"]["mae"] <= results["E02_full"]["mae"]

    # E04 — scaling only matters for scale-sensitive models (Ridge); trees are invariant.
    for sname, scaler in [("none", None), ("standard", StandardScaler()), ("minmax", MinMaxScaler()), ("robust", RobustScaler())]:
        results[f"E04_ridge_{sname}"] = run("E04", f"Ridge, {sname} scaling", RemainingTimeModel(make_prep(scaler=scaler), Ridge(alpha=1.0), use_log),
                                            Xtr, ytr, Xva, yva, {"scaler": sname, "log_target": use_log})
    results["E04_hgb_standard"] = run("E04", "HistGB, standard scaling (control)", RemainingTimeModel(make_prep(scaler=StandardScaler()), hgb(), use_log),
                                      Xtr, ytr, Xva, yva, {"scaler": "standard", "log_target": use_log})

    # E05 — bagged tree ensembles
    n_trees = 100 if quick else 300
    for name, est in [("RandomForest", RandomForestRegressor), ("ExtraTrees", ExtraTreesRegressor)]:
        results[f"E05_{name}"] = run("E05", name, RemainingTimeModel(make_prep(), est(n_estimators=n_trees, min_samples_leaf=5, max_features=0.5,
                                                                                      n_jobs=-1, random_state=SEED), use_log),
                                     Xtr, ytr, Xva, yva, {"n_estimators": n_trees, "min_samples_leaf": 5, "max_features": 0.5, "log_target": use_log})

    # E06 — XGBoost with defaults + early stopping on validation
    xgb_modes = {"log1p target, squared error": ({}, True), "raw target, absolute error": ({"objective": "reg:absoluteerror"}, False)}
    for mode, (kw, lg) in xgb_modes.items():
        results[f"E06_{mode}"] = run("E06", f"XGBoost {mode}", RemainingTimeModel(make_prep(), xgb(**kw), lg), Xtr, ytr, Xva, yva,
                                     {**kw, "log_target": lg})
    xgb_mode = min(xgb_modes, key=lambda m: results[f"E06_{m}"]["mae"])
    xgb_kw, xgb_log = xgb_modes[xgb_mode]

    # E07 — random search over the XGBoost hyperparameters, early stopping on validation
    rng = np.random.default_rng(SEED)
    space = {"max_depth": [4, 6, 8, 10], "learning_rate": [0.02, 0.05, 0.1], "min_child_weight": [1, 5, 20, 50],
             "subsample": [0.6, 0.8, 1.0], "colsample_bytree": [0.5, 0.7, 0.9], "reg_alpha": [0, 0.1, 1, 5],
             "reg_lambda": [0.5, 1, 5, 10]}
    best = (np.inf, None, None)
    for i in range(6 if quick else 25):
        params = {k: (v[rng.integers(len(v))]) for k, v in space.items()}
        params = {k: (float(v) if isinstance(v, np.floating) else int(v) if isinstance(v, np.integer) else v) for k, v in params.items()}
        mdl = RemainingTimeModel(make_prep(), xgb(**params, **xgb_kw), xgb_log)
        m = run("E07", f"XGBoost tuned trial {i:02d}", mdl, Xtr, ytr, Xva, yva, {**params, **xgb_kw, "log_target": xgb_log})
        if m["mae"] < best[0]:
            best = (m["mae"], params, mdl)
    best_params, best_xgb = best[1], best[2]
    results["E07_best"] = regression_metrics(yva, best_xgb.predict(Xva))
    log_run("E07", "regression", "XGBoost tuned (best trial)", results["E07_best"],
            {**best_params, **xgb_kw, "best_iteration": int(best_xgb.model.best_iteration), "log_target": xgb_log},
            best_xgb.feature_names, len(Xtr), len(Xva))

    # Serve the learned model with the best validation MAE (the test set decides nothing here).
    winner = min(FITTED, key=lambda k: FITTED[k][0])
    final = FITTED[winner][1]
    winner_key = winner
    joblib.dump(final, MODELS / "regressor.joblib")
    meta = {"model": winner_key, "estimator": type(final.model).__name__, "log_target": final.log_target,
            "xgb_best_params": best_params, "dropped_gt_7d_from_train": bool(drop_long),
            "val_metrics": regression_metrics(yva, final.predict(Xva)), "baseline_val_metrics": results["E00_berth"],
            "features": final.feature_names}
    (MODELS / "regressor.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps({k: round(v["mae"], 3) for k, v in results.items()}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="fewer trees and search trials, for a fast smoke run")
    main(**vars(ap.parse_args()))
