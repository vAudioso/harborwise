"""PortPulse API (BE4).

Run:  uvicorn api.main:app --reload        (docs at http://127.0.0.1:8000/docs)

Replay mode: "now" is any 2019 UTC timestamp (`as_of`). The API finds the commercial ships
actually alongside a berth at that moment and forecasts when a slot frees up, using only
information observable at `as_of`.
"""
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from portpulse.clearance import ClearanceService
from portpulse.config import CLEAR_WITHIN_H, EXPERIMENTS_CSV, REPORTS
from portpulse.fuel import PROFILES, profile, profiles_as_dicts
from portpulse.optimizer import DEFAULT_FUEL_PRICE, DEFAULT_LAMBDA, DEFAULT_MU, explain, recommend

DEMO_AS_OF = "2019-11-15T12:00:00"
STATE: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        STATE["svc"] = ClearanceService()
    except FileNotFoundError as e:  # models/data not built yet: start anyway, explain on each call
        STATE["error"] = str(e)
    yield
    STATE.clear()


app = FastAPI(title="PortPulse API", version="1.0.0", lifespan=lifespan,
              description="Berth-clearance forecasts and arrival-speed recommendations (replay mode over 2019 Caribbean AIS data).")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

VesselType = Literal["cont", "tank", "bulk", "gcar", "crui"]


def svc() -> ClearanceService:
    if "svc" not in STATE:
        raise HTTPException(503, STATE.get("error", "service not ready") + " Build the data and models with `python -m pipeline.run_all`.")
    return STATE["svc"]


def clean(obj):
    """Make numpy/pandas values JSON-safe."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items() if k != "samples"}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if not np.isfinite(obj) else round(float(obj), 4)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj


class ClearanceRequest(BaseModel):
    berth_id: str = Field(..., examples=["335_26#1293"], description="Berth key from GET /berths/{port_id}")
    as_of: datetime = Field(default=datetime.fromisoformat(DEMO_AS_OF), description="UTC time inside 2019")


class RecommendRequest(ClearanceRequest):
    vessel_type: VesselType = Field("cont", description="Type of the incoming ship")
    distance_nm: float = Field(..., gt=0, le=3000, examples=[180], description="Sailing distance to the berth (nautical miles)")
    speed_min: float | None = Field(None, gt=0, le=30, description="Lowest acceptable speed (kn); defaults to the vessel profile")
    speed_max: float | None = Field(None, gt=0, le=30, description="Highest acceptable speed (kn); defaults to the vessel profile")
    fuel_price_usd_per_t: float = Field(DEFAULT_FUEL_PRICE, gt=0)
    lambda_usd_per_ship_h: float | None = Field(DEFAULT_LAMBDA, ge=0, description="Value of one hour of the ship's time "
                                                "(default: implied so that service speed is optimal without congestion)")
    mu_usd_per_idle_h: float = Field(DEFAULT_MU, ge=0, description="Cost of one hour the berth stands free before arrival")


def _forecast(berth_id: str, as_of) -> dict:
    s = svc()
    try:
        return s.predict(berth_id, as_of)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/health")
def health():
    return {"status": "ok" if "svc" in STATE else "models_missing", "detail": STATE.get("error"), "demo_as_of": DEMO_AS_OF}


@app.get("/ports")
def ports():
    s = svc()
    from portpulse.data import load_ports
    return clean(load_ports().sort_values("visits", ascending=False).to_dict(orient="records")) if s else []


@app.get("/berths/{port_id}")
def berths(port_id: int, include_polygon: bool = True):
    b = svc().berths.reset_index()
    b = b[b["port_id"] == port_id]
    if b.empty:
        raise HTTPException(404, f"no commercial berths for port {port_id}")
    recs = b.sort_values("visits", ascending=False).to_dict(orient="records")
    for r in recs:
        r["polygon"] = json.loads(r["polygon"]) if include_polygon else None
    return clean(recs)


@app.get("/occupied")
def occupied(as_of: datetime = Query(datetime.fromisoformat(DEMO_AS_OF)), port_id: int | None = None):
    """Berths with commercial ships alongside at as_of — handy for picking a demo berth."""
    try:
        occ = svc().occupied_berths(as_of, port_id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return clean(occ.sort_values(["full", "occupants"], ascending=False).to_dict(orient="records"))


@app.post("/predict/clearance")
def predict_clearance(req: ClearanceRequest):
    """P25/P50/P90 of when a slot at the berth frees up, plus per-occupant forecasts."""
    out = _forecast(req.berth_id, req.as_of)
    out["note"] = (f"Quantiles are hours from as_of. p_leaves_within_{CLEAR_WITHIN_H}h is a calibrated probability. "
                   "Replay mode: only information observable at as_of is used.")
    return clean(out)


@app.post("/recommend")
def recommend_speed(req: RecommendRequest):
    """Recommended speed, ETA, expected wait, fuel and CO2 vs sailing at service speed."""
    fc = _forecast(req.berth_id, req.as_of)
    prof = profile(req.vessel_type)
    samples = fc["samples"]
    try:
        rec = recommend(prof, req.distance_nm, samples, req.speed_min, req.speed_max,
                        req.fuel_price_usd_per_t, req.lambda_usd_per_ship_h, req.mu_usd_per_idle_h)
    except ValueError as e:
        raise HTTPException(422, str(e))
    as_of = pd.Timestamp(fc["as_of"])
    best, base = rec["recommended"], rec["baseline"]

    def view(c):
        d = c.as_dict()
        d["eta"] = (as_of + pd.Timedelta(hours=c.sailing_h)).isoformat(timespec="minutes")
        return d

    return clean({
        "berth_id": req.berth_id, "as_of": fc["as_of"], "vessel_profile": prof.__dict__,
        "clearance": {"status": fc["status"], "hours": fc["clearance_h"], "time": fc["clearance_time"],
                      "capacity": fc["capacity"], "occupants": fc["occupants"]},
        "recommended": view(best), "baseline_service_speed": view(base),
        "vs_baseline": {"fuel_saved_t": base.total_fuel_t - best.total_fuel_t,
                        "co2_saved_t": base.co2_t - best.co2_t,
                        "wait_reduced_h": base.expected_wait_h - best.expected_wait_h,
                        "cost_saved_usd": base.total_cost_usd - best.total_cost_usd},
        "candidates": [view(c) for c in rec["candidates"]],
        "weights": rec["weights"],
        "why": explain(rec, fc["clearance_h"]),
        "label": "SIMULATED estimate: fuel uses illustrative engine profiles (see /vessel-profiles).",
    })


@app.get("/vessel-profiles")
def vessel_profiles():
    return {"profiles": profiles_as_dicts(), "co2_factor_t_per_t_fuel": 3.114,
            "source": "cubic speed law (Psaraftis & Kontovas 2013); CO2 factor IMO MEPC.308(73). Engine figures are illustrative."}


@app.get("/experiments")
def experiments(task: str | None = None, exp_id: str | None = None):
    if not EXPERIMENTS_CSV.exists():
        return []
    df = pd.read_csv(EXPERIMENTS_CSV)
    if task:
        df = df[df["task"] == task]
    if exp_id:
        df = df[df["exp_id"] == exp_id]
    return clean(df.replace({np.nan: None}).to_dict(orient="records"))


@app.get("/experiments/summary")
def experiments_summary():
    out = {}
    for name in ("E10_final_test.json", "E11_simulation.json"):
        p = REPORTS / name
        if p.exists():
            out[name.split(".")[0]] = json.loads(p.read_text())
    return out


@app.get("/")
def root():
    return {"name": "PortPulse API", "docs": "/docs", "vessel_types": sorted(PROFILES), "demo_as_of": DEMO_AS_OF}
