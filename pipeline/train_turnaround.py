"""Turnaround time at arrival: how long will this ship stay alongside, predicted the moment it berths?

Compares Random Forest, HistGradientBoosting and GradientBoosting with the global-median and
port-median baselines (MAE and RMSE in hours). Each model picks its target (log1p + squared
error, or raw hours + absolute error) on Sep–Oct validation; the test set (Nov–Dec) is scored once.

Usage: python -m pipeline.train_turnaround
"""
import json

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor, RandomForestRegressor  # noqa: E402

from harborwise.config import MODELS, REPORTS, SEED  # noqa: E402
from harborwise.data import load_port_calls, load_visits  # noqa: E402
from harborwise.features import build_checkpoints  # noqa: E402
from harborwise.models import MedianBaseline, RemainingTimeModel, make_prep  # noqa: E402
from harborwise.tracking import Timer, log_run, regression_metrics, reset_experiments  # noqa: E402


def metrics(y, p) -> dict:
    m = regression_metrics(y, p)
    err = np.abs(y - p)
    m.update(within_1h=float(np.mean(err <= 1)), within_3h=float(np.mean(err <= 3)), within_6h=float(np.mean(err <= 6)))
    return m


def candidates():
    rf = lambda: RandomForestRegressor(n_estimators=300, min_samples_leaf=5, max_features=0.5, n_jobs=-1, random_state=SEED)  # noqa: E731
    return {
        "Random Forest": [("log1p target", rf, True), ("raw target", rf, False)],
        "HistGradientBoosting": [
            ("log1p target", lambda: HistGradientBoostingRegressor(max_iter=600, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=30,
                                                                   l2_regularization=1.0, random_state=SEED), True),
            ("raw target, absolute loss", lambda: HistGradientBoostingRegressor(loss="absolute_error", max_iter=600, learning_rate=0.05,
                                                                                max_leaf_nodes=63, min_samples_leaf=30, random_state=SEED), False)],
        "GradientBoosting": [
            ("log1p target", lambda: GradientBoostingRegressor(n_estimators=500, learning_rate=0.05, max_depth=5, subsample=0.8,
                                                               min_samples_leaf=20, random_state=SEED), True),
            ("raw target, absolute loss", lambda: GradientBoostingRegressor(loss="absolute_error", n_estimators=500, learning_rate=0.05,
                                                                            max_depth=5, subsample=0.8, min_samples_leaf=20, random_state=SEED), False)],
    }


def main():
    reset_experiments(("T00", "T01", "T02"))
    rows = build_checkpoints(load_visits(), load_port_calls(), checkpoints=(0,))
    tr, va, te = (rows[rows["split"] == s] for s in ("train", "val", "test"))
    tr = tr[~tr["flag_gt_7d"]]  # E01 finding: long lay-ups hurt training; val/test keep them
    ytr, yva, yte = (d["remaining_h"].to_numpy() for d in (tr, va, te))

    results, fitted = {}, {}
    for level, label in (("global", "Global median"), ("port", "Port median"), ("berth", "Berth median (extra baseline)")):
        b = MedianBaseline(level).fit(tr, ytr)
        results[label] = {"val": metrics(yva, b.predict(va)), "test": metrics(yte, b.predict(te)), "kind": "baseline"}
        log_run("T00", "turnaround", label, results[label]["val"], n_train=len(tr), n_eval=len(va))

    for name, options in candidates().items():
        best = None
        for opt, make, log in options:
            mdl = RemainingTimeModel(make_prep(), make(), log)
            with Timer() as tm:
                mdl.fit(tr, ytr)
            m = metrics(yva, mdl.predict(va))
            log_run("T01", "turnaround", f"{name}, {opt}", m, {"log_target": log}, mdl.feature_names, len(tr), len(va), train_seconds=tm.seconds)
            if best is None or m["mae"] < best[0]["mae"]:
                best = (m, mdl, opt)
        fitted[name] = best[1]
        results[name] = {"val": best[0], "test": metrics(yte, best[1].predict(te)), "kind": "model", "target": best[2]}

    for name, r in results.items():
        log_run("T02", "turnaround", f"TEST {name}", r["test"], n_train=len(tr), n_eval=len(te), eval_split="test")

    winner = min((k for k in results if results[k]["kind"] == "model"), key=lambda k: results[k]["val"]["mae"])
    joblib.dump(fitted[winner], MODELS / "turnaround.joblib")
    pred = fitted[winner].predict(te)
    by_type = (pd.DataFrame({"type": te["vesseltype"].to_numpy(), "err": np.abs(pred - yte), "y": yte})
               .groupby("type").agg(rows=("err", "size"), mae=("err", "mean"), median_abs_err=("err", "median"),
                                    within_1h=("err", lambda e: float(np.mean(e <= 1))), median_stay_h=("y", "median")).round(2))
    summary = {"rows": {"train": len(tr), "val": len(va), "test": len(te)}, "winner": winner, "results": results,
               "winner_by_type_test": by_type.to_dict(orient="index"),
               "test_median_turnaround_h": float(np.median(yte))}
    (MODELS / "turnaround.json").write_text(json.dumps({"winner": winner, "target": results[winner]["target"],
                                                         "val": results[winner]["val"], "test": results[winner]["test"]}, indent=2))
    (REPORTS / "turnaround_comparison.json").write_text(json.dumps(summary, indent=2, default=str))
    write_report(summary, by_type)
    chart(results)
    for k, r in results.items():
        print(f"{k:<32} test MAE {r['test']['mae']:6.2f} h   RMSE {r['test']['rmse']:6.2f} h   within 1 h {r['test']['within_1h']:.1%}")


def chart(results):
    names = list(results)
    mae = [results[n]["test"]["mae"] for n in names]
    rmse = [results[n]["test"]["rmse"] for n in names]
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=130)
    x = np.arange(len(names))
    ax.bar(x - 0.2, mae, 0.4, label="MAE", color="#0b5f8a")
    ax.bar(x + 0.2, rmse, 0.4, label="RMSE", color="#b9c8d3")
    for i, v in enumerate(mae):
        ax.text(i - 0.2, v + 0.5, f"{v:.1f}", ha="center", fontsize=8)
    ax.set_xticks(x, [n.replace(" (extra baseline)", "\n(extra)") for n in names], fontsize=8)
    ax.set_ylabel("Hours (test set)")
    ax.set_title("Turnaround time predicted at arrival: test MAE / RMSE")
    ax.legend(frameon=False)
    fig.tight_layout()
    (REPORTS / "figures").mkdir(exist_ok=True)
    fig.savefig(REPORTS / "figures" / "turnaround_mae_rmse.png")
    plt.close(fig)


def write_report(S, by_type):
    R = S["results"]
    lines = ["# Turnaround time at arrival: model comparison", "",
             f"Predict how long a commercial ship will stay alongside, at the moment it berths. Train Jan–Aug ({S['rows']['train']:,} visits, "
             f"stays over 7 days excluded), validation Sep–Oct ({S['rows']['val']:,}), test Nov–Dec ({S['rows']['test']:,}, scored once). "
             f"Median turnaround in the test set: {S['test_median_turnaround_h']:.1f} h.", "",
             "| Model | Test MAE (h) | Test RMSE (h) | Median abs. error (h) | Within 1 h | Within 3 h | Validation MAE (h) |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for k, r in R.items():
        t, v = r["test"], r["val"]
        name = f"**{k}**" if k == S["winner"] else k
        lines.append(f"| {name} | {t['mae']:.2f} | {t['rmse']:.2f} | {t['medae']:.2f} | {t['within_1h']:.1%} | {t['within_3h']:.1%} | {v['mae']:.2f} |")
    lines += ["", f"Best model (chosen on validation): **{S['winner']}** ({R[S['winner']]['target']}).", "",
              "## Best model by vessel type (test)", "", by_type.to_markdown(), "",
              "## Why the MAE is not under 1 hour",
              "Stays are long and highly variable (median about a day, with a long tail of multi-day stays). The data has no cargo volume, "
              "crane, labour or schedule information, which is what actually decides when a ship leaves. An average error of under an hour "
              "would need those inputs, or information from after arrival (which would be leakage). See the remaining-time model "
              "(E10 report): errors shrink as the stay goes on, because elapsed time is informative.", ""]
    (REPORTS / "turnaround_comparison.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
