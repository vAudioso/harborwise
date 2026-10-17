"""Step 7 (BE4): E11 — replay test-period berth occupancies and compare speed strategies.

Scenario per test checkpoint (berth with one slot and one commercial occupant):
  * at time t the occupant has been alongside for k hours (1, 3 or 6);
  * the incoming ship is the next commercial ship that actually used this berth, with its real
    vessel type. Its distance is set from a service-speed ETA drawn uniformly from an ETA window
    (main run 2–30 h; sensitivity runs 2–12 h and 12–48 h), capped at 400 nm;
  * strategies:  baseline  = sail at service speed, wait at anchor if needed
                 portpulse = speed chosen by the optimizer from the model's P25/P50/P90
                 oracle    = speed chosen with the TRUE departure time (upper bound)
  * outcomes are scored against the occupant's real departure time.
Everything is SIMULATED: the incoming ship's position is hypothetical and fuel uses the
illustrative engine profiles in portpulse/fuel.py.

Usage: python -m pipeline.simulate [--scenarios 4000]
"""
import argparse
import json

import joblib
import numpy as np
import pandas as pd

from portpulse.config import MODELS, REPORTS, SEED
from portpulse.data import load_berths, load_checkpoints, load_visits
from portpulse.fuel import anchor_fuel_t, co2_t, profile, voyage_fuel_t
from portpulse.optimizer import implied_time_value, recommend, samples_from_quantiles
from portpulse.tracking import log_run, reset_experiments


def realised(prof, d, v, clear_true_h, price, lam, mu):
    lam = implied_time_value(prof, price) if lam is None else lam
    sail = d / v
    wait, idle = max(0.0, clear_true_h - sail), max(0.0, sail - clear_true_h)
    fuel = voyage_fuel_t(prof, v, d) + anchor_fuel_t(prof, wait)
    return {"speed_kn": v, "wait_h": wait, "idle_h": idle, "time_to_berth_h": sail + wait, "fuel_t": fuel, "co2_t": co2_t(fuel),
            "waited": wait > 0, "cost_usd": fuel * price + lam * (sail + wait) + mu * idle}


def scenarios(n: int) -> pd.DataFrame:
    cp = load_checkpoints()
    test = cp[(cp["split"] == "test") & cp["elapsed_h"].isin([1, 3, 6]) & (cp["berth_occupancy_others"] == 0)]
    berths = load_berths().set_index("berth_id")
    test = test[test["berth_id"].map(berths["capacity"]) == 1]
    # Next commercial ship to use the same berth after the occupant arrived.
    v = load_visits().sort_values("arrival_time")
    nxt = v.groupby("berth_id")["vesseltype"].shift(-1)
    test = test.merge(pd.DataFrame({"visit_id": v["visit_id"], "incoming_type": nxt}), on="visit_id", how="left")
    test = test.dropna(subset=["incoming_type"])
    test = test.groupby("visit_id").sample(1, random_state=SEED)  # one scenario per occupant visit
    return test.sample(min(n, len(test)), random_state=SEED).reset_index(drop=True)


def run_scenarios(sc, Q, eta_window, price, lam, mu) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    eta = rng.uniform(*eta_window, len(sc))
    rows = []
    for i, r in sc.iterrows():
        prof = profile(r["incoming_type"])
        d = round(min(400.0, eta[i] * prof.design_speed_kn), 1)
        true_c = float(r["remaining_h"])
        samples = samples_from_quantiles(*Q[i], n=400)
        rec = recommend(prof, d, samples, fuel_price=price, lam=lam, mu=mu)
        oracle = recommend(prof, d, np.array([true_c]), fuel_price=price, lam=lam, mu=mu)
        out = {"scenario": i, "visit_id": r["visit_id"], "port_id": r["port_id"], "berth_id": r["berth_id"],
               "incoming_type": r["incoming_type"], "distance_nm": d, "true_clearance_h": true_c,
               "p25": Q[i, 0], "p50": Q[i, 1], "p90": Q[i, 2]}
        for name, v in (("baseline", rec["baseline"].speed_kn), ("portpulse", rec["recommended"].speed_kn),
                        ("oracle", oracle["recommended"].speed_kn)):
            for k, val in realised(prof, d, v, true_c, price, lam, mu).items():
                out[f"{name}_{k}"] = val
        rows.append(out)
    return pd.DataFrame(rows)


def summarise(df):
    def summary(name):
        return {"mean_wait_h": df[f"{name}_wait_h"].mean(), "share_waiting": df[f"{name}_waited"].mean(),
                "mean_idle_h": df[f"{name}_idle_h"].mean(), "mean_time_to_berth_h": df[f"{name}_time_to_berth_h"].mean(), "total_fuel_t": df[f"{name}_fuel_t"].sum(),
                "total_co2_t": df[f"{name}_co2_t"].sum(), "mean_speed_kn": df[f"{name}_speed_kn"].mean(),
                "total_cost_usd": df[f"{name}_cost_usd"].sum()}

    S = {k: summary(k) for k in ("baseline", "portpulse", "oracle")}
    S["scenarios"] = len(df)
    b, p, o = S["baseline"], S["portpulse"], S["oracle"]
    S["portpulse_vs_baseline"] = {
        "fuel_saving_pct": 100 * (1 - p["total_fuel_t"] / b["total_fuel_t"]),
        "co2_saving_t": b["total_co2_t"] - p["total_co2_t"],
        "wait_reduction_pct": 100 * (1 - p["mean_wait_h"] / b["mean_wait_h"]) if b["mean_wait_h"] else 0.0,
        "extra_idle_h_per_call": p["mean_idle_h"] - b["mean_idle_h"],
        "extra_time_to_berth_h_per_call": p["mean_time_to_berth_h"] - b["mean_time_to_berth_h"],
        "cost_saving_pct": 100 * (1 - p["total_cost_usd"] / b["total_cost_usd"]),
        "share_of_oracle_cost_saving_captured": (b["total_cost_usd"] - p["total_cost_usd"]) / max(1e-9, b["total_cost_usd"] - o["total_cost_usd"]),
    }
    S["by_type"] = (df.groupby("incoming_type")
                    .apply(lambda g: pd.Series({"scenarios": len(g),
                                                "fuel_saving_pct": 100 * (1 - g["portpulse_fuel_t"].sum() / g["baseline_fuel_t"].sum()),
                                                "baseline_mean_wait_h": g["baseline_wait_h"].mean(),
                                                "portpulse_mean_wait_h": g["portpulse_wait_h"].mean()}), include_groups=False)
                    .round(2).to_dict(orient="index"))
    return S


def main(n_scenarios: int = 4000, price: float = 650.0, lam: float | None = None, mu: float = 500.0):
    reset_experiments(("E11",))
    sc = scenarios(n_scenarios)
    Q = joblib.load(MODELS / "quantile.joblib").predict(sc)
    windows = {"main (ETA 2–30 h)": (2, 30), "close in (ETA 2–12 h)": (2, 12), "far out (ETA 12–48 h)": (12, 48)}
    runs = {name: run_scenarios(sc, Q, w, price, lam, mu) for name, w in windows.items()}
    runs["main (ETA 2–30 h)"].to_csv(REPORTS / "E11_simulation_scenarios.csv", index=False)
    S = summarise(runs["main (ETA 2–30 h)"])
    S["sensitivity"] = {name: summarise(df)["portpulse_vs_baseline"] | {"baseline_mean_wait_h": float(df["baseline_wait_h"].mean())}
                        for name, df in runs.items()}
    S["assumptions"] = {"scenarios": len(sc), "eta_window_h": "service-speed ETA uniform 2–30 h (distance = ETA x service speed, max 400 nm)",
                        "fuel_price_usd_per_t": price,
                        "lambda_usd_per_ship_h": "implied per vessel type (2 x service-speed daily fuel cost / 24)" if lam is None else lam, "mu_usd_per_idle_h": mu,
                        "fuel_model": "cubic speed law, illustrative per-type profiles (portpulse/fuel.py)",
                        "period": "test (Nov–Dec 2019)", "label": "SIMULATED — not measured savings"}
    for name in ("baseline", "portpulse", "oracle"):
        log_run("E11", "simulation", name, {k: float(v) for k, v in S[name].items()}, S["assumptions"], n_eval=len(sc), eval_split="test")
    (REPORTS / "E11_simulation.json").write_text(json.dumps(S, indent=2, default=float))
    write_report(S)
    print(json.dumps(S["portpulse_vs_baseline"], indent=2))


def write_report(S):
    b, p, o, c = S["baseline"], S["portpulse"], S["oracle"], S["portpulse_vs_baseline"]
    a = S["assumptions"]
    sens = "\n".join(f"| {n} | {v['baseline_mean_wait_h']:.1f} | {v['fuel_saving_pct']:.1f}% | {v['wait_reduction_pct']:.1f}% | "
                     f"{v['extra_idle_h_per_call']:+.2f} | {v['cost_saving_pct']:.1f}% | {v['share_of_oracle_cost_saving_captured']:.0%} |"
                     for n, v in S["sensitivity"].items())
    rows = "\n".join(f"| {t} | {v['scenarios']:.0f} | {v['baseline_mean_wait_h']:.1f} | {v['portpulse_mean_wait_h']:.1f} | {v['fuel_saving_pct']:.1f}% |"
                     for t, v in S["by_type"].items())
    md = f"""# E11 — Arrival-speed simulation (SIMULATED)

{a['scenarios']:,} replayed scenarios from the test period ({a['period']}). Each one: a real commercial ship is alongside a
single-slot berth; the next ship that really used that berth is on its way ({a['eta_window_h']}) and must pick a speed.
Outcomes are scored against the occupant's real departure time.

| Strategy | Mean speed (kn) | Mean wait at anchor (h) | Share that wait | Mean berth idle before arrival (h) | Fuel (t) | CO₂ (t) |
|---|---:|---:|---:|---:|---:|---:|
| Baseline: service speed | {b['mean_speed_kn']:.1f} | {b['mean_wait_h']:.1f} | {b['share_waiting']:.0%} | {b['mean_idle_h']:.1f} | {b['total_fuel_t']:,.0f} | {b['total_co2_t']:,.0f} |
| **PortPulse** | **{p['mean_speed_kn']:.1f}** | **{p['mean_wait_h']:.1f}** | **{p['share_waiting']:.0%}** | **{p['mean_idle_h']:.1f}** | **{p['total_fuel_t']:,.0f}** | **{p['total_co2_t']:,.0f}** |
| Oracle (knows true departure) | {o['mean_speed_kn']:.1f} | {o['mean_wait_h']:.1f} | {o['share_waiting']:.0%} | {o['mean_idle_h']:.1f} | {o['total_fuel_t']:,.0f} | {o['total_co2_t']:,.0f} |

**Simulated effect of PortPulse vs baseline:** fuel −{c['fuel_saving_pct']:.1f}%, CO₂ −{c['co2_saving_t']:,.0f} t over the scenarios,
anchorage wait −{c['wait_reduction_pct']:.1f}%, berth idle {c['extra_idle_h_per_call']:+.2f} h per call, ship's time to berth {c['extra_time_to_berth_h_per_call']:+.2f} h per call,
total cost −{c['cost_saving_pct']:.1f}%. Because ship time is valued so that service speed is optimal without congestion, these savings come from
avoiding waits (just-in-time arrival), not from generic slow steaming.
PortPulse captures {c['share_of_oracle_cost_saving_captured']:.0%} of the cost saving a perfect forecast would give.

| Incoming type | Scenarios | Baseline wait (h) | PortPulse wait (h) | Fuel saving |
|---|---:|---:|---:|---:|
{rows}

**Sensitivity to how far out the ship is when it decides:**

| ETA window | Baseline mean wait (h) | Fuel saving | Wait reduction | Extra berth idle (h/call) | Cost saving | Share of oracle saving |
|---|---:|---:|---:|---:|---:|---:|
{sens}

**Assumptions (read before quoting any number):** fuel price ${a['fuel_price_usd_per_t']:.0f}/t; ship time valued at {a['lambda_usd_per_ship_h']};
berth-idle cost ${a['mu_usd_per_idle_h']:.0f}/h; {a['fuel_model']}. The incoming ship's distance is hypothetical, weather/currents/
port slot rules are ignored, and the data cannot measure real anchorage waits (Phase 1 audit §6). These are simulated savings.
"""
    (REPORTS / "E11_simulation.md").write_text(md)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=4000, dest="n_scenarios")
    main(**vars(ap.parse_args()))
