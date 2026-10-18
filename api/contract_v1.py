"""Website contract v1.0: the routes the HarborWise website calls.

    POST /recommendations   speed recommendation for one voyage, from the trained clearance model
    GET  /experiments       test-set results for the evaluation page
    GET  /data-quality      dataset audit and EDA counts
    GET  /figures/{name}    report figures (PNG)

The request/response shapes match the validators built into the website (web/index.html).
Replay mode: planning_time_utc must fall in 2019, the period of the dataset.
"""
import json
import platform
import time
from datetime import datetime

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from harborwise.config import CLEAR_WITHIN_H, EXPERIMENTS_CSV, PROCESSED, REPORTS, SEGMENT_CONFIDENCE, SEGMENT_OF, seg_path
from harborwise.fuel import CO2_PER_T_FUEL, VesselProfile, anchor_fuel_t, profile, voyage_fuel_t
from harborwise.optimizer import DEFAULT_MU

router = APIRouter()
HEADLINE = "liner"  # the evaluation page shows the headline segment

VESSEL_TYPES = {"container vessel": "cont", "container ship": "cont", "cruise ship": "crui", "cruise": "crui",
                "tanker": "tank", "bulk carrier": "bulk", "general cargo": "gcar",
                "cont": "cont", "crui": "crui", "tank": "tank", "bulk": "bulk", "gcar": "gcar"}

# The website's demo destinations. Cartagena, Kingston and San Juan have port calls in the dataset but
# no ship positions, so no berth visits can be rebuilt there; the API uses the nearest port with berth
# data instead and says so in every response.
PORT_SLUGS = {
    "houston": (353, None),
    "colon": (129, None),
    "cartagena": (134, "Cartagena has no ship positions in the 2019 data; using Mamonal, its industrial port in the same bay (4 nm)"),
    "kingston": (240, "Kingston has no ship positions in the 2019 data; using Port Esquivel, the nearest Jamaican port with berth data (19 nm, little traffic)"),
    "sanjuan": (76, "San Juan has no ship positions in the 2019 data; using St Thomas, the nearest port with substantial traffic (66 nm)"),
}


def runtime() -> dict:
    return {"platform": f"{platform.system()} {platform.machine()}", "machine": platform.node(),
            "python": platform.python_version()}


class SpeedRange(BaseModel):
    min_kn: float = Field(..., gt=0, le=40)
    max_kn: float = Field(..., gt=0, le=40)
    step_kn: float = Field(0.5, ge=0.1, le=5)


class RecommendationRequest(BaseModel):
    schema_version: str = "1.0"
    vessel_id: str = "HW-001"
    vessel_type: str = "Container vessel"
    daily_fuel_t: float = Field(..., gt=0, le=1000, description="Main-engine fuel per day at the baseline speed")
    destination_port_id: str | int = Field(..., description="Website slug, port name, or numeric port_id")
    distance_nm: float = Field(..., gt=0, le=5000)
    baseline_speed_kn: float = Field(..., gt=0, le=40)
    speed_range: SpeedRange
    arrival_flexibility_h: float = Field(8, ge=0, le=240)
    max_late_risk: float = Field(0.2, ge=0, le=1)
    fuel_price_usd_t: float = Field(620, gt=0, le=10000)
    planning_time_utc: datetime
    berth_id: str | None = None
    lambda_usd_per_ship_h: float | None = Field(None, ge=0)
    mu_usd_per_idle_h: float | None = Field(None, ge=0)


def _svc():
    from api.main import svc  # the service is loaded once at startup in api.main
    return svc()


def _resolve_port(dest, berths: pd.DataFrame) -> tuple[int, str | None]:
    key = str(dest).strip()
    if key.lower() in PORT_SLUGS:
        return PORT_SLUGS[key.lower()]
    if key.isdigit():
        pid = int(key)
    else:
        names = berths.drop_duplicates("port_id").set_index("portname")["port_id"]
        hit = [p for n, p in names.items() if n.lower() == key.lower()]
        if not hit:
            raise HTTPException(404, f"no data for destination {dest!r}: the 2019 dataset covers the Caribbean and Gulf of Mexico only. "
                                     f"Use a slug ({', '.join(PORT_SLUGS)}), a port name from GET /ports, or a port_id; "
                                     "for other ports use the website's offline sample")
        pid = int(hit[0])
    if pid not in set(berths["port_id"]):
        raise HTTPException(404, f"port {pid} has no berth-level data in the 2019 dataset")
    return pid, None


def _pick_berth(s, port_id: int, vtype: str, t: pd.Timestamp, requested: str | None) -> tuple[pd.Series, str]:
    """Destination berth, in order of preference:
    a full berth used mainly by this ship type -> a full berth of this ship's segment (liner / other)
    -> the most occupied berth of this type -> the busiest berth of this type -> the busiest berth in the port."""
    b = s.berths.reset_index()
    if requested:
        if requested not in set(b["berth_id"]):
            raise HTTPException(404, f"unknown berth_id {requested!r}")
        return b.set_index("berth_id").loc[requested].rename(requested), "the berth you asked for"
    here = b[b["port_id"] == port_id].copy()
    occ = s.occupied_berths(t, port_id).set_index("berth_id")["occupants"]
    here["occupants"] = here["berth_id"].map(occ).fillna(0).astype(int)
    here["full"] = here["occupants"] >= here["capacity"]
    seg = SEGMENT_OF[vtype]
    same = here[here["main_type"] == vtype]
    same_seg = here[here["main_type"].map(SEGMENT_OF) == seg]
    label = {"liner": "container/cruise", "other": "tanker/bulk/general-cargo"}[seg]
    options = [
        (same[same["full"]], "a full berth used mainly by this ship type"),
        (same_seg[same_seg["full"]], f"a full berth used mainly by {label} ships (no berth of this exact type is full)"),
        (same[same["occupants"] > 0], "the most occupied berth used mainly by this ship type (none is full)"),
        (same, "the busiest berth used mainly by this ship type (none is occupied at the planning time)"),
        (here, "the busiest berth in the port (none is used mainly by this ship type)"),
    ]
    for pool, why in options:
        if len(pool):
            row = pool.sort_values(["occupants", "visits"], ascending=False).iloc[0]
            return row.rename(row["berth_id"]), why
    raise HTTPException(404, f"port {port_id} has no berths")


def _score(p: VesselProfile, d: float, v: float, C: np.ndarray, price: float, lam: float, mu: float, flex: float) -> dict:
    sail = d / v
    wait = float(np.maximum(0.0, C - sail).mean())
    idle = float(np.maximum(0.0, sail - C).mean())
    late = float((C < sail - flex).mean())  # berth stood free for longer than the arrival flexibility
    fuel = voyage_fuel_t(p, v, d) + anchor_fuel_t(p, wait)
    return {"speed_kn": round(float(v), 2), "sailing_h": sail, "wait_h": wait, "idle_h": idle, "fuel_t": fuel,
            "co2_t": fuel * CO2_PER_T_FUEL, "late_risk": late, "total_cost_usd": fuel * price + lam * (sail + wait) + mu * idle}


@router.post("/recommendations")
def recommendations(req: RecommendationRequest):
    t0 = time.perf_counter()
    s = _svc()
    vtype = VESSEL_TYPES.get(req.vessel_type.strip().lower())
    if vtype is None:
        raise HTTPException(422, f"unknown vessel_type {req.vessel_type!r}; expected one of {sorted(set(VESSEL_TYPES))}")
    if req.speed_range.min_kn > req.speed_range.max_kn:
        raise HTTPException(422, "speed_range.min_kn must not exceed max_kn")
    try:
        t = s.check_time(req.planning_time_utc)
    except ValueError as e:
        raise HTTPException(422, str(e))

    port_id, stand_in = _resolve_port(req.destination_port_id, s.berths.reset_index())
    berth, why = _pick_berth(s, port_id, vtype, t, req.berth_id)
    berth_id = str(berth.name)
    t_model = time.perf_counter()
    fc = s.predict(berth_id, t)
    model_ms = (time.perf_counter() - t_model) * 1000
    C = np.asarray(fc["samples"], dtype=float)

    base_prof = profile(vtype)
    prof = VesselProfile(vtype, base_prof.label, req.baseline_speed_kn, req.daily_fuel_t, base_prof.anchor_daily_fuel_t,
                         req.speed_range.min_kn, req.speed_range.max_kn)
    price = req.fuel_price_usd_t
    lam = req.lambda_usd_per_ship_h if req.lambda_usd_per_ship_h is not None else 2 * req.daily_fuel_t * price / 24
    mu = req.mu_usd_per_idle_h if req.mu_usd_per_idle_h is not None else DEFAULT_MU
    if fc["status"] == "free":
        # A slot is free now, but the model cannot see ships that will arrive before this one does, so
        # "free now" is no reason to rush: no idle-berth penalty, and the ship keeps its economic speed.
        mu = 0.0
    flex = req.arrival_flexibility_h

    lo, hi, st = req.speed_range.min_kn, req.speed_range.max_kn, req.speed_range.step_kn
    grid = list(np.round(np.arange(lo, hi + 1e-8, st), 2))
    if not grid or abs(grid[-1] - hi) > 1e-6:
        grid.append(round(hi, 2))
    if lo <= req.baseline_speed_kn <= hi and not any(abs(g - req.baseline_speed_kn) < 1e-6 for g in grid):
        grid = sorted(grid + [req.baseline_speed_kn])

    base = _score(prof, req.distance_nm, req.baseline_speed_kn, C, price, lam, mu, flex)
    cap = max(req.max_late_risk, base["late_risk"])
    eta = lambda h: (t + pd.Timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    cands = []
    for v in grid:
        c = _score(prof, req.distance_nm, float(v), C, price, lam, mu, flex)
        c["feasible"] = c["late_risk"] <= cap + 1e-9
        c["eta_utc"] = eta(c["sailing_h"])
        cands.append(c)
    feasible = [c for c in cands if c["feasible"]]
    best = min(feasible, key=lambda c: c["total_cost_usd"]) if feasible else None
    base.update(feasible=True, eta_utc=eta(base["sailing_h"]))

    q = fc["clearance_h"]
    conf = fc.get("confidence", SEGMENT_CONFIDENCE.get(SEGMENT_OF.get(vtype, "other"), "lower"))
    if best:
        saved = base["fuel_t"] - best["fuel_t"]
        explanation = (f"{best['speed_kn']:.1f} kn has the lowest total cost (fuel + ship time + idle berth) with late risk "
                       f"{best['late_risk']:.0%} (limit {cap:.0%}). The berth is forecast to free in {q['p25']:.1f}–{q['p90']:.1f} h "
                       f"(P25–P90). Versus {req.baseline_speed_kn:g} kn: {saved:+.1f} t fuel saved, expected wait "
                       f"{base['wait_h']:.1f} → {best['wait_h']:.1f} h. Forecast confidence: {conf}.")
    else:
        explanation = "No speed in the range keeps the late risk under the limit. Widen the speed range or raise the flexibility."
    if fc["status"] == "free":
        explanation += (" A slot at this berth is free at the planning time, so there is no queue to time the arrival"
                        " against; the plan keeps the ship's economic speed rather than rushing for a slot that may be"
                        " taken before it arrives.")
    if stand_in:
        explanation += f" Note: {stand_in}."

    poly = json.loads(berth["polygon"]) if isinstance(berth.get("polygon"), str) else None
    return _clean({
        "schema_version": "1.0",
        "request": json.loads(req.model_dump_json()),
        "provenance": {"mode": "backend", "source": "HarborWise API · trained clearance model", **runtime(),
                       "quantiles": "trained model (replay of 2019 data)", "fuel": "simulated",
                       "confidence": conf, "stand_in_port": stand_in},
        "clearance": {"p25_h": q["p25"], "p50_h": q["p50"], "p90_h": q["p90"], "status": fc["status"],
                      "capacity": fc["capacity"], "occupants": fc["occupants"], "confidence": conf,
                      "event": "Berth slot becomes available", "time_origin_utc": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "provenance": "trained_model", f"p_leaves_within_{CLEAR_WITHIN_H}h_by_occupant":
                          [o.get(f"p_leaves_within_{CLEAR_WITHIN_H}h") for o in fc["occupants"]]},
        "berth": {"berth_id": berth_id, "port_id": int(berth["port_id"]), "portname": berth["portname"],
                  "lat": float(berth["lat"]), "lon": float(berth["lon"]), "capacity": int(berth["capacity"]),
                  "visits_2019": int(berth["visits"]), "median_stay_h": float(berth["median_stay_h"]),
                  "main_type": berth["main_type"], "polygon": poly[:1] if poly else None,
                  "why_chosen": why + (f" ({stand_in})" if stand_in else "")},
        "candidates": cands,
        "recommended_speed_kn": best["speed_kn"] if best else None,
        "baseline": {**base, "speed_kn": req.baseline_speed_kn},
        "risk_limit_applied": cap,
        "weights": {"fuel_price_usd_per_t": price, "lambda_usd_per_ship_h": lam, "mu_usd_per_idle_h": mu},
        "explanation": explanation,
        "timing_ms": {"model": round(model_ms, 1), "total": round((time.perf_counter() - t0) * 1000, 1)},
    })


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if k != "samples"}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if not np.isfinite(obj) else round(float(obj), 4)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


def _read(path):
    if not path.exists():
        raise HTTPException(503, f"{path.name} is missing. Run `python -m pipeline.run_all` first.")
    return json.loads(path.read_text())


SAMPLER_LABEL = {"none": "No resampling", "class_weight": "Class weights", "random_over": "Random oversampling",
                 "random_under": "Random undersampling", "smote": "SMOTE", "tomek": "Tomek links", "smote_tomek": "SMOTE + Tomek"}


@router.get("/experiments")
def experiments():
    seg = HEADLINE
    e10 = _read(seg_path(REPORTS, "E10_final_test.json", seg))
    turn = _read(seg_path(REPORTS, "turnaround_comparison.json", seg))
    sim = _read(seg_path(REPORTS, "E11_simulation.json", seg))
    models = [{"name": f"{name} (stay predicted at arrival)", "mae_h": r["test"]["mae"], "rmse_h": r["test"]["rmse"],
               "medae_h": r["test"]["medae"], "within_1h": r["test"]["within_1h"], "provenance": "measured"}
              for name, r in turn["results"].items()]
    rt = e10["regression"]
    remaining = [{"name": label, "mae_h": rt[k]["mae"], "rmse_h": rt[k]["rmse"], "medae_h": rt[k]["medae"], "provenance": "measured"}
                 for k, label in (("baseline_global", "Global median × checkpoint"), ("baseline_port", "Port median × checkpoint"),
                                  ("baseline_berth", "Berth median × checkpoint"), ("model", "XGBoost (tuned)"))]

    imbalance = []
    if EXPERIMENTS_CSV.exists():
        ex = pd.read_csv(EXPERIMENTS_CSV)
        ex = ex[(ex["segment"] == seg) & (ex["task"] == "classification") & ex["exp_id"].isin(["E08", "E09"])]
        for _, r in ex.iterrows():
            model, _, sampler = str(r["model"]).partition(" | ")
            if model == "RandomForest" and sampler in SAMPLER_LABEL:
                imbalance.append({"strategy": SAMPLER_LABEL[sampler], "pr_auc": float(r["pr_auc"]), "recall": float(r["recall"]),
                                  "provenance": "measured", "split": "val"})
    clf = e10["classification"]
    cal = clf["calibrated_at_threshold"]
    best_base = min(rt["baseline_global"]["mae"], rt["baseline_port"]["mae"], rt["baseline_berth"]["mae"])
    turn_win = turn["results"][turn["winner"]]["test"]["mae"]
    port_med = turn["results"]["Port median"]["test"]["mae"]
    return _clean({
        "schema_version": "1.0",
        "segment": {"name": seg, "types": ["container", "cruise"], "confidence": "high"},
        "source": f"HarborWise backend · reports/turnaround_comparison_{seg}.json, reports/E10_final_test_{seg}.json, experiments/experiments.csv",
        "status": "measured_on_held_out_test_set",
        "models": remaining,  # the site charts these as "hours until the berth clears"
        "turnaround_models": models,  # stay predicted at arrival: RF / HGB / GB vs medians (figure: turnaround_mae_rmse.png)
        "imbalance": imbalance,
        "calibration": {"target": f"Clears within {CLEAR_WITHIN_H} h · test set · isotonic-calibrated", "provenance": "measured",
                        "bins": clf.get("calibration_bins", []), "ece": cal["ece"], "brier": cal["brier"],
                        "figure": "/figures/classification_pr_calibration.png"},
        "classification": {**cal, "positive_rate": clf["positive_rate"], "model": clf["model"]},
        "quantile": e10["quantile"],
        "unseen_ports": e10["unseen_ports"],
        "improvement_vs_best_baseline_pct": round(100 * (1 - rt["model"]["mae"] / best_base), 1),
        "turnaround_improvement_vs_port_median_pct": round(100 * (1 - turn_win / port_med), 1),
        "simulation": sim,
        "evaluation": {"split": "Chronological · train Jan–Aug, validation Sep–Oct, test Nov–Dec 2019",
                       "sample_count": e10["test_rows"], "data_version": "Iphar et al. 2024 · Zenodo 10380638 v1.1.0",
                       "target": "Hours until a container or cruise ship leaves its berth, predicted 1–24 h after it arrives",
                       "note": "Models were chosen on validation; the test set was used once (E10)."},
        "figures": [f"/figures/{n}" for n in ("turnaround_mae_rmse.png", "classification_pr_calibration.png", "quantile_coverage.png",
                                              "regression_mae_by_type.png", "regression_pred_vs_actual.png")],
    })


TYPE_LABEL = {"tank": "Tanker", "cont": "Container", "bulk": "Bulk carrier", "gcar": "General cargo", "crui": "Cruise"}


@router.get("/data-quality")
def data_quality():
    from harborwise.data import load_ports, load_visits
    v = load_visits()
    audit = _read(REPORTS / "phase1" / "berth_audit.json")
    summary = _read(PROCESSED / "dataset_summary.json")
    bm = audit["berth_match"]
    by_type = v["vesseltype"].value_counts()
    ports = load_ports().set_index("port_id")["portname"]
    by_port = v["port_id"].value_counts().head(12)
    return _clean({
        "schema_version": "1.0",
        "duration_distribution": {"provenance": "measured", "title": "Commercial berth visits by vessel type (2019)",
                                  "bins": [{"label": TYPE_LABEL[k], "count": int(n)} for k, n in by_type.items()]},
        "visits_per_port": {"provenance": "measured", "title": "Commercial berth visits, 12 busiest ports (2019)",
                            "ports": [{"name": str(ports.get(pid, pid)), "count": int(n)} for pid, n in by_port.items()]},
        "berth_match": {"percent": bm["match_rate_among_candidates_pct"], "provenance": "measured",
                        "matched_count": bm["matched_calls"], "total_count": bm["calls_with_coords_at_ports_with_berths"],
                        "corr_with_published_counts": bm["our_counts_vs_published_number_corr"]},
        "dataset": {"url": "https://zenodo.org/records/10380638", "period": "2019", "region": "Caribbean and Gulf of Mexico",
                    "timezone": "UTC", "ingested": True, "license": "CC BY-NC-SA 4.0",
                    "citation": "Iphar et al., Data in Brief (2024), Zenodo 10380638 v1.1.0", **summary},
        "record_definitions": [
            {"record": "Port call", "meaning": "A stop below 0.5 kn within about 600 m of a surveyed quay. It is a stay alongside, not an anchorage wait."},
            {"record": "Berth visit", "meaning": "Port calls matched to a berth polygon, merged when the gap is under 1 h. Commercial ships with confidence ≥ 0.5 only."},
            {"record": "Checkpoint", "meaning": "A ship observed 1/3/6/12/24 h after it berthed. The label is the hours left until it leaves."},
            {"record": "Clearance quantile", "meaning": "P25/P50/P90 of the hours until a slot at the berth frees, from the planning time."},
            {"record": "Segment", "meaning": "Liner ships (container, cruise) are the headline, high-confidence models; tankers, bulk and general cargo use separate, lower-confidence models."},
        ],
    })


@router.get("/figures/{name}")
def figures(name: str):
    if "/" in name or "\\" in name or ".." in name or not name.endswith(".png"):
        raise HTTPException(404, "not found")
    folder = REPORTS / "figures"
    for candidate in (folder / name, seg_path(folder, name, HEADLINE)):
        if candidate.exists():
            return FileResponse(candidate, media_type="image/png")
    raise HTTPException(404, f"figure {name} not found")
