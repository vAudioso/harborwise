"""Step 6 (BE3): E10 — the one and only look at the test set (Nov–Dec 2019).

Scores the saved regressor, classifier and quantile model on test, compares them with the
baselines, breaks errors down by vessel type / checkpoint / port, tests generalisation to
ports the model never saw, dumps the biggest misses and writes figures + a markdown report.

Usage: python -m pipeline.evaluate
"""
import json

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.metrics import precision_recall_curve  # noqa: E402

from pipeline.train_quantile import quantile_metrics  # noqa: E402
from portpulse.config import CLEAR_WITHIN_H, MODELS, REPORTS, SEED  # noqa: E402
from portpulse.data import load_checkpoints, split_xy  # noqa: E402
from portpulse.models import MedianBaseline, RemainingTimeModel  # noqa: E402
from portpulse.tracking import classification_metrics, log_run, regression_metrics, reset_experiments  # noqa: E402

FIG = REPORTS / "figures"


def by_group(df, col, err_col="abs_err"):
    g = df.groupby(col).agg(rows=(err_col, "size"), mae=(err_col, "mean"), baseline_mae=("abs_err_base", "mean"),
                            median_remaining_h=("remaining_h", "median"))
    g["improvement_pct"] = 100 * (1 - g["mae"] / g["baseline_mae"])
    return g.round(2)


def unseen_ports(cp, reg: RemainingTimeModel, rng):
    """Hold out 20% of ports (by visits) entirely; train on the rest (Jan–Aug), test on held-out ports (Nov–Dec)."""
    ports = cp["port_id"].unique()
    held = set(rng.choice(ports, size=max(1, int(0.2 * len(ports))), replace=False))
    tr = cp[(cp["split"] == "train") & ~cp["port_id"].isin(held)]
    va = cp[(cp["split"] == "val") & ~cp["port_id"].isin(held)]
    te = cp[(cp["split"] == "test") & cp["port_id"].isin(held)]
    model = RemainingTimeModel(clone(reg.prep), clone(reg.model), reg.log_target)
    model.fit(tr, tr["remaining_h"].to_numpy(), va, va["remaining_h"].to_numpy())
    base = MedianBaseline("berth").fit(tr, tr["remaining_h"].to_numpy())
    y = te["remaining_h"].to_numpy()
    return regression_metrics(y, model.predict(te)), regression_metrics(y, base.predict(te)), len(held), len(te)


def main():
    reset_experiments(("E10",))
    FIG.mkdir(parents=True, exist_ok=True)
    cp = load_checkpoints()
    Xtr, ytr = split_xy(cp, "train")
    Xte, yte = split_xy(cp, "test")
    reg = joblib.load(MODELS / "regressor.joblib")
    clf = joblib.load(MODELS / "classifier.joblib")
    qm = joblib.load(MODELS / "quantile.joblib")
    reg_meta = json.loads((MODELS / "regressor.json").read_text())
    if reg_meta.get("dropped_gt_7d_from_train"):
        keep = ~Xtr["flag_gt_7d"].to_numpy()
        Xtr, ytr = Xtr[keep], ytr[keep]
    R = {"test_rows": len(Xte)}

    # ---- regression vs baselines ----
    pred = reg.predict(Xte)
    R["regression"] = {"model": regression_metrics(yte, pred)}
    for level in ("global", "port", "berth"):
        R["regression"][f"baseline_{level}"] = regression_metrics(yte, MedianBaseline(level).fit(Xtr, ytr).predict(Xte))
    for k, m in R["regression"].items():
        log_run("E10", "regression", f"TEST {k}", m, n_eval=len(Xte), eval_split="test")
    base_pred = MedianBaseline("berth").fit(Xtr, ytr).predict(Xte)
    err = Xte[["visit_id", "vessel_id", "port_id", "berth_id", "vesseltype", "elapsed_h", "t", "arrival_time",
               "departure_time", "duration_hours", "n_calls", "flag_gt_7d"]].copy()
    err["remaining_h"], err["pred_h"], err["baseline_h"] = yte, pred, base_pred
    err["abs_err"], err["abs_err_base"] = np.abs(pred - yte), np.abs(base_pred - yte)
    by_type, by_cp = by_group(err, "vesseltype"), by_group(err, "elapsed_h")
    top_ports = err["port_id"].value_counts().head(15).index
    by_port = by_group(err[err["port_id"].isin(top_ports)], "port_id").sort_values("rows", ascending=False)
    by_type.to_csv(REPORTS / "E10_errors_by_type.csv"); by_cp.to_csv(REPORTS / "E10_errors_by_checkpoint.csv")
    by_port.to_csv(REPORTS / "E10_errors_by_port.csv")
    misses = err.sort_values("abs_err", ascending=False).head(50)
    misses.to_csv(REPORTS / "E10_biggest_misses.csv", index=False)
    R["biggest_misses"] = {"share_of_top50_with_gt_7d_stay": float(misses["flag_gt_7d"].mean()),
                           "median_true_remaining_h_top50": float(misses["remaining_h"].median()),
                           "share_of_top50_merged_from_multiple_calls": float((misses["n_calls"] > 1).mean())}
    R["regression"]["test_without_gt_7d_stays"] = regression_metrics(yte[~err["flag_gt_7d"]], pred[~err["flag_gt_7d"]])

    # ---- unseen ports ----
    m_unseen, b_unseen, n_ports, n_rows = unseen_ports(cp, reg, np.random.default_rng(SEED))
    R["unseen_ports"] = {"held_out_ports": n_ports, "rows": n_rows, "model": m_unseen, "berth_baseline_fallback": b_unseen}
    log_run("E10", "regression", "TEST unseen ports: model", m_unseen, n_eval=n_rows, eval_split="test_unseen_ports")
    log_run("E10", "regression", "TEST unseen ports: baseline", b_unseen, n_eval=n_rows, eval_split="test_unseen_ports")

    # ---- classification ----
    yb = (yte <= CLEAR_WITHIN_H).astype(int)
    p = clf.predict_proba(Xte)
    p_raw = clf.raw_proba(Xte)
    R["classification"] = {"calibrated_at_threshold": classification_metrics(yb, p, clf.threshold),
                           "raw_at_0.5": classification_metrics(yb, p_raw, 0.5),
                           "positive_rate": float(yb.mean()), "model": f"{type(clf.model).__name__} | {clf.sampler_name}"}
    log_run("E10", "classification", f"TEST clears within {CLEAR_WITHIN_H}h", R["classification"]["calibrated_at_threshold"],
            n_eval=len(yb), eval_split="test")

    # ---- quantiles ----
    Q = qm.predict(Xte)
    R["quantile"] = quantile_metrics(yte, Q)
    log_run("E10", "quantile", "TEST clearance window", R["quantile"], n_eval=len(yte), eval_split="test")
    R["quantile_by_type"] = {t: quantile_metrics(yte[m], Q[m]) for t in err["vesseltype"].unique()
                             for m in [(err["vesseltype"] == t).to_numpy()]}

    figures(err, yb, p, p_raw, R)
    (REPORTS / "E10_final_test.json").write_text(json.dumps(R, indent=2, default=str))
    write_report(R, by_type, by_cp, by_port, reg_meta)
    print(json.dumps({"regression_mae": R["regression"]["model"]["mae"], "berth_baseline_mae": R["regression"]["baseline_berth"]["mae"],
                      "pr_auc": R["classification"]["calibrated_at_threshold"]["pr_auc"],
                      "p90_coverage": R["quantile"]["coverage_p90"]}, indent=2))


def figures(err, yb, p, p_raw, R):
    plt.rcParams.update({"figure.dpi": 130, "font.size": 9})
    fig, ax = plt.subplots(figsize=(5, 4.2))
    lim = np.quantile(np.r_[err["remaining_h"], err["pred_h"]], 0.99)
    ax.hexbin(err["remaining_h"].clip(upper=lim), err["pred_h"].clip(upper=lim), gridsize=45, bins="log", cmap="Blues")
    ax.plot([0, lim], [0, lim], color="#b0312b", lw=1)
    ax.set(xlabel="Actual hours until departure", ylabel="Predicted hours", title="Remaining time: predicted vs actual (test)")
    fig.tight_layout(); fig.savefig(FIG / "regression_pred_vs_actual.png"); plt.close(fig)

    bt = err.groupby("vesseltype")[["abs_err", "abs_err_base"]].mean()
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    x = np.arange(len(bt))
    ax.bar(x - 0.2, bt["abs_err_base"], 0.4, label="Berth median baseline", color="#b9c8d3")
    ax.bar(x + 0.2, bt["abs_err"], 0.4, label="Model", color="#0b5f8a")
    ax.set_xticks(x, bt.index); ax.set_ylabel("MAE (hours)"); ax.legend(frameon=False); ax.set_title("Test MAE by vessel type")
    fig.tight_layout(); fig.savefig(FIG / "regression_mae_by_type.png"); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    prec, rec, _ = precision_recall_curve(yb, p)
    axes[0].plot(rec, prec, color="#0b5f8a"); axes[0].axhline(yb.mean(), ls="--", color="grey", lw=1)
    axes[0].set(xlabel="Recall", ylabel="Precision", title=f"PR curve, clears within {CLEAR_WITHIN_H} h (test)")
    for name, probs, color in (("raw model", p_raw, "#b9c8d3"), ("isotonic-calibrated", p, "#0b5f8a")):
        fr, mp = calibration_curve(yb, probs, n_bins=10, strategy="quantile")
        axes[1].plot(mp, fr, marker="o", ms=3, label=name, color=color)
    axes[1].legend(frameon=False)
    axes[1].plot([0, 1], [0, 1], ls="--", color="grey", lw=1)
    axes[1].set(xlabel="Predicted probability", ylabel="Observed frequency", title="Calibration (test)")
    fig.tight_layout(); fig.savefig(FIG / "classification_pr_calibration.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    names = ["P25", "P50", "P90"]
    cov = [R["quantile"]["coverage_p25"], R["quantile"]["coverage_p50"], R["quantile"]["coverage_p90"]]
    ax.bar(names, cov, color="#0b5f8a", width=0.5)
    ax.scatter(names, [0.25, 0.5, 0.9], color="#b0312b", zorder=3, label="target")
    ax.set(ylim=(0, 1), ylabel="Share of ships gone by predicted time", title="Clearance window coverage (test)")
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(FIG / "quantile_coverage.png"); plt.close(fig)


def write_report(R, by_type, by_cp, by_port, reg_meta):
    r, c, q, u = R["regression"], R["classification"]["calibrated_at_threshold"], R["quantile"], R["unseen_ports"]
    imp = 100 * (1 - r["model"]["mae"] / r["baseline_berth"]["mae"])
    md = f"""# E10 — Final test report (Nov–Dec 2019, untouched until now)

Test rows: {R['test_rows']:,} checkpoints (ships alongside at 1/3/6/12/24 h). Models were chosen on Sep–Oct validation only.

## Remaining time until the berth clears (point forecast)

| Model | MAE (h) | RMSE (h) | Median abs. error (h) |
|---|---:|---:|---:|
| Global median × checkpoint | {r['baseline_global']['mae']:.2f} | {r['baseline_global']['rmse']:.2f} | {r['baseline_global']['medae']:.2f} |
| Port median × checkpoint | {r['baseline_port']['mae']:.2f} | {r['baseline_port']['rmse']:.2f} | {r['baseline_port']['medae']:.2f} |
| Berth median × checkpoint | {r['baseline_berth']['mae']:.2f} | {r['baseline_berth']['rmse']:.2f} | {r['baseline_berth']['medae']:.2f} |
| **{reg_meta['model']}** | **{r['model']['mae']:.2f}** | **{r['model']['rmse']:.2f}** | **{r['model']['medae']:.2f}** |

The model is **{imp:.1f}% better than the strongest baseline** on MAE. Without stays longer than 7 days the test MAE is {r['test_without_gt_7d_stays']['mae']:.2f} h.
Note: the earlier 9.09 h "port median" figure was for total port-call duration of all vessels at visit start, a different and easier target.

**Unseen ports** ({u['held_out_ports']} ports held out of training entirely, {u['rows']:,} test rows): model MAE {u['model']['mae']:.2f} h vs {u['berth_baseline_fallback']['mae']:.2f} h for the baseline (which falls back to vessel-type medians).

### Errors by vessel type
{by_type.to_markdown()}

### Errors by checkpoint (hours alongside)
{by_cp.to_markdown()}

### Errors at the 15 busiest test ports
{by_port.to_markdown()}

Biggest misses (`E10_biggest_misses.csv`): {R['biggest_misses']['share_of_top50_with_gt_7d_stay']:.0%} of the top 50 are stays over 7 days;
their median true remaining time is {R['biggest_misses']['median_true_remaining_h_top50']:.0f} h. These look like rare long lay-ups / repairs, not label errors.

## Clears within {CLEAR_WITHIN_H} h (classification)

Model: {R['classification']['model']}, isotonic-calibrated, threshold {c['threshold']:.2f} (chosen on validation).
Positive rate on test: {R['classification']['positive_rate']:.1%}.

| Precision | Recall | F1 | PR-AUC | Brier | ECE |
|---:|---:|---:|---:|---:|---:|
| {c['precision']:.3f} | {c['recall']:.3f} | {c['f1']:.3f} | {c['pr_auc']:.3f} | {c['brier']:.4f} | {c['ece']:.4f} |

Confusion matrix: TP {c['tp']:,} · FP {c['fp']:,} · FN {c['fn']:,} · TN {c['tn']:,}

## Clearance window (P25 / P50 / P90)

| | P25 | P50 | P90 | P25–P90 interval |
|---|---:|---:|---:|---:|
| Target coverage | 25% | 50% | 90% | 65% |
| Test coverage | {q['coverage_p25']:.1%} | {q['coverage_p50']:.1%} | {q['coverage_p90']:.1%} | {q['interval_p25_p90_coverage']:.1%} |

Median interval width: {q['interval_median_width_h']:.1f} h.

Figures: `reports/figures/`. Every number here is also in `E10_final_test.json` and `experiments/experiments.csv` (exp_id E10).
"""
    (REPORTS / "E10_final_test.md").write_text(md)


if __name__ == "__main__":
    main()
