"""Step 4 (BE3): "berth clears within N hours" classifier, experiments E08–E09.

E08: natural class balance (overall and per port) + three models without resampling.
E09: class weighting and six resampling strategies x three models. Resampling is applied to
     the training matrix only; validation keeps its real distribution. SMOTE/Tomek work on
     standardised features (distance-based), with vessel type kept categorical (SMOTENC).
The winner (validation PR-AUC) is recalibrated (isotonic) on untouched validation data and
gets a decision threshold chosen there.

Usage: python -m pipeline.train_classification [--quick]
"""
import argparse
import json

import joblib
import numpy as np
import pandas as pd
from imblearn.combine import SMOTETomek
from imblearn.over_sampling import SMOTENC, RandomOverSampler
from imblearn.under_sampling import RandomUnderSampler, TomekLinks
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from harborwise.config import CLEAR_WITHIN_H, MODELS, REPORTS, SEED
from harborwise.data import load_checkpoints, split_xy
from harborwise.models import ClearWithinClassifier, make_prep
from harborwise.tracking import Timer, classification_metrics, log_run, reset_experiments


def resample(name, Z: pd.DataFrame, y: np.ndarray, vt_idx: int):
    """Return a resampled copy of (Z, y) in original feature units."""
    if name in ("none", "class_weight"):
        return Z, y
    if name == "random_over":
        return RandomOverSampler(random_state=SEED).fit_resample(Z, y)
    if name == "random_under":
        return RandomUnderSampler(random_state=SEED).fit_resample(Z, y)
    scaler = StandardScaler().fit(Z)
    Zs = scaler.transform(Z)
    smote = SMOTENC(categorical_features=[vt_idx], random_state=SEED, k_neighbors=5)
    sampler = {"smote": smote, "tomek": TomekLinks(n_jobs=-1),
               "smote_tomek": SMOTETomek(smote=smote, tomek=TomekLinks(n_jobs=-1), random_state=SEED)}[name]
    Zr, yr = sampler.fit_resample(Zs, y)
    Zr = pd.DataFrame(scaler.inverse_transform(Zr), columns=Z.columns)
    Zr["vt_code"] = Zr["vt_code"].round()
    return Zr, yr


def make_model(kind: str, class_weight: bool, pos_weight: float, quick: bool):
    if kind == "LogReg":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0,
                                                                  class_weight="balanced" if class_weight else None)), True
    if kind == "RandomForest":
        return RandomForestClassifier(n_estimators=100 if quick else 250, min_samples_leaf=5, max_features="sqrt", n_jobs=-1,
                                      class_weight="balanced" if class_weight else None, random_state=SEED), False
    return XGBClassifier(n_estimators=1500, learning_rate=0.05, max_depth=6, min_child_weight=5, subsample=0.8,
                         colsample_bytree=0.8, tree_method="hist", early_stopping_rounds=75, eval_metric="aucpr",
                         scale_pos_weight=pos_weight if class_weight else 1.0, random_state=SEED, n_jobs=-1), False


def best_threshold(y, p):
    grid = np.linspace(0.05, 0.95, 91)
    f1 = [classification_metrics(y, p, t)["f1"] for t in grid]
    return float(grid[int(np.argmax(f1))])


def main(quick: bool = False):
    reset_experiments(("E08", "E09"))
    cp = load_checkpoints()
    Xtr, rtr = split_xy(cp, "train")
    Xva, rva = split_xy(cp, "val")
    ytr, yva = (rtr <= CLEAR_WITHIN_H).astype(int), (rva <= CLEAR_WITHIN_H).astype(int)

    # Class balance overall and by port (top 20 ports by rows).
    bal = (cp.assign(pos=(cp["remaining_h"] <= CLEAR_WITHIN_H).astype(int))
           .groupby(["split", "port_id"])["pos"].agg(["size", "mean"]).reset_index())
    bal.to_csv(REPORTS / "class_balance_by_port.csv", index=False)
    pos_rate = float(ytr.mean())
    print(f"positive rate (clears within {CLEAR_WITHIN_H} h): train {pos_rate:.3f}, val {yva.mean():.3f}")

    prep = make_prep()  # FeatureBuilder + median imputer; fitted on training rows only
    prep.fit(Xtr, rtr)
    Ztr = prep.transform(Xtr)
    cols = list(Ztr.columns)
    vt_idx = cols.index("vt_code")
    pos_weight = (1 - pos_rate) / pos_rate

    samplers = ["none", "class_weight", "random_over", "random_under", "smote", "tomek", "smote_tomek"]
    kinds = ["LogReg", "RandomForest", "XGBoost"]
    runs = []
    for s in samplers:
        with Timer() as ts:
            Zr, yr = resample(s, Ztr, ytr, vt_idx)
        for k in kinds:
            model, onehot = make_model(k, s == "class_weight", pos_weight, quick)
            clf = ClearWithinClassifier(prep, model, onehot, s)
            M = ClearWithinClassifier.expand_vt(Zr, cols) if onehot else np.asarray(Zr)
            with Timer() as tm:
                if k == "XGBoost":
                    Mv = clf._matrix(prep.transform(Xva))
                    model.fit(M, yr, eval_set=[(Mv, yva)], verbose=False)
                else:
                    model.fit(M, yr)
            p = clf.raw_proba(Xva)
            m = classification_metrics(yva, p, 0.5)
            exp = "E08" if s == "none" else "E09"
            log_run(exp, "classification", f"{k} | {s}", m, {"sampler": s, "train_rows_after_resampling": int(len(yr)),
                                                             "positive_share_after_resampling": round(float(np.mean(yr)), 4),
                                                             "N_hours": CLEAR_WITHIN_H},
                    cols, len(yr), len(yva), train_seconds=tm.seconds + ts.seconds)
            runs.append((m["pr_auc"], k, s, clf))

    runs.sort(key=lambda r: -r[0])
    pr_auc, kind, sampler, best = runs[0]
    p_val = best.raw_proba(Xva)
    best.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(p_val, yva)
    p_cal = best.predict_proba(Xva)
    best.threshold = best_threshold(yva, p_cal)
    cal_m = classification_metrics(yva, p_cal, best.threshold)
    log_run("E09", "classification", f"{kind} | {sampler} | isotonic + tuned threshold", cal_m,
            {"sampler": sampler, "threshold": best.threshold, "calibration": "isotonic on validation"}, cols, None, len(yva),
            notes="calibration and threshold fitted on validation; honest numbers are in E10 (test)")
    joblib.dump(best, MODELS / "classifier.joblib")
    meta = {"model": kind, "sampler": sampler, "N_hours": CLEAR_WITHIN_H, "threshold": best.threshold,
            "val_pr_auc_raw": pr_auc, "val_metrics_calibrated": cal_m, "train_positive_rate": pos_rate,
            "ranking": [{"model": k, "sampler": s, "val_pr_auc": round(a, 4)} for a, k, s, _ in runs]}
    (MODELS / "classifier.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps({k: meta[k] for k in ("model", "sampler", "threshold", "val_pr_auc_raw")}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(**vars(ap.parse_args()))
