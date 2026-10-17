"""Clearance service: who is alongside a berth at a moment, and when will a slot free up?

Runs in replay mode over the 2019 data: "now" (as_of) is any 2019 timestamp, the current
occupants are the ships actually alongside then, and every feature is computed from what was
observable at as_of. Their real departure times are never used for prediction.
"""
from dataclasses import dataclass
from functools import cached_property

import joblib
import numpy as np
import pandas as pd

from harborwise.config import CHECKPOINTS_H, CLEAR_WITHIN_H, MODELS, QUANTILES
from harborwise.data import load_berths, load_port_calls, load_visits
from harborwise.features import VT_CODE, context_features, time_features, vessel_history
from harborwise.optimizer import berth_free_samples, samples_from_quantiles

YEAR_START, YEAR_END = pd.Timestamp("2019-01-01"), pd.Timestamp("2019-12-31 23:59:59")


@dataclass
class Occupant:
    visit_id: int | None
    vessel_id: int | None
    vesseltype: str
    arrival_time: pd.Timestamp


class ClearanceService:
    def __init__(self, models_dir=MODELS):
        self.regressor = joblib.load(models_dir / "regressor.joblib")
        self.quantile = joblib.load(models_dir / "quantile.joblib")
        self.classifier = joblib.load(models_dir / "classifier.joblib")
        self.visits = load_visits()
        self.port_calls = load_port_calls()
        self.berths = load_berths().set_index("berth_id")

    @cached_property
    def history(self) -> pd.DataFrame:
        return vessel_history(self.visits).set_index("visit_id")

    @staticmethod
    def check_time(as_of) -> pd.Timestamp:
        t = pd.Timestamp(as_of)
        if t.tzinfo is not None:
            t = t.tz_convert("UTC").tz_localize(None)
        if not (YEAR_START <= t <= YEAR_END):
            raise ValueError("as_of must be inside 2019 (the replay period of the dataset), in UTC")
        return t

    def berth(self, berth_id: str) -> pd.Series:
        if berth_id not in self.berths.index:
            raise KeyError(f"unknown berth_id {berth_id!r}")
        return self.berths.loc[berth_id]

    def occupants_at(self, berth_id: str, as_of) -> list[Occupant]:
        t = self.check_time(as_of)
        v = self.visits
        here = v[(v["berth_id"] == berth_id) & (v["arrival_time"] <= t) & (v["departure_time"] > t)]
        return [Occupant(int(r.visit_id), int(r.vessel_id), r.vesseltype, r.arrival_time) for r in here.itertuples()]

    def occupied_berths(self, as_of, port_id: int | None = None) -> pd.DataFrame:
        t = self.check_time(as_of)
        v = self.visits
        m = (v["arrival_time"] <= t) & (v["departure_time"] > t)
        if port_id is not None:
            m &= v["port_id"] == port_id
        occ = v[m].groupby("berth_id").agg(occupants=("visit_id", "size"), port_id=("port_id", "first"))
        occ = occ.join(self.berths[["capacity", "portname"]])
        occ["full"] = occ["occupants"] >= occ["capacity"]
        return occ.reset_index()

    def feature_rows(self, berth_id: str, as_of, occupants: list[Occupant]) -> pd.DataFrame:
        t = self.check_time(as_of)
        b = self.berth(berth_id)
        rows = pd.DataFrame({
            "visit_id": [o.visit_id for o in occupants],
            "vessel_id": [o.vessel_id for o in occupants],
            "berth_id": berth_id, "port_id": int(b["port_id"]),
            "vesseltype": [o.vesseltype for o in occupants],
            "arrival_time": pd.to_datetime([o.arrival_time for o in occupants]),
        })
        rows["t"] = t
        rows["elapsed_h"] = ((t - rows["arrival_time"]).dt.total_seconds() / 3600).clip(lower=0)
        rows = pd.concat([rows, time_features(rows["t"], rows["arrival_time"])], axis=1)
        rows["vt_code"] = rows["vesseltype"].map(VT_CODE)
        hist = self.history.reindex(rows["visit_id"]).reset_index(drop=True)
        rows = pd.concat([rows, hist.drop(columns=[c for c in hist.columns if c == "visit_id"], errors="ignore")], axis=1)
        in_table = rows["visit_id"].notna().to_numpy()
        rows = pd.concat([rows, context_features(rows, self.visits, self.port_calls, in_table)], axis=1)
        return rows

    def predict(self, berth_id: str, as_of, extra_occupant: Occupant | None = None) -> dict:
        """Clearance forecast for one berth at as_of."""
        t = self.check_time(as_of)
        b = self.berth(berth_id)
        occupants = self.occupants_at(berth_id, t)
        if extra_occupant is not None:
            occupants.append(extra_occupant)
        capacity = int(b["capacity"])
        out = {"berth_id": berth_id, "port_id": int(b["port_id"]), "portname": b["portname"], "as_of": t.isoformat(),
               "capacity": capacity, "occupants": [], "status": "free"}
        if not occupants:
            out["clearance_h"] = {"p25": 0.0, "p50": 0.0, "p90": 0.0}
            out["clearance_time"] = {k: t.isoformat() for k in ("p25", "p50", "p90")}
            out["samples"] = np.zeros(1)
            return out

        X = self.feature_rows(berth_id, t, occupants)
        Q = self.quantile.predict(X)
        point = self.regressor.predict(X)
        p_clear = self.classifier.predict_proba(X)
        samples = []
        for i, o in enumerate(occupants):
            q = dict(zip(("p25", "p50", "p90"), map(float, Q[i])))
            samples.append(samples_from_quantiles(q["p25"], q["p50"], q["p90"]))
            out["occupants"].append({
                "visit_id": o.visit_id, "vessel_type": o.vesseltype,
                "arrival_time": pd.Timestamp(o.arrival_time).isoformat(),
                "elapsed_h": round(float(X.loc[i, "elapsed_h"]), 2),
                "elapsed_beyond_training_range": bool(X.loc[i, "elapsed_h"] > max(CHECKPOINTS_H) * 2),
                "remaining_h": {k: round(v, 2) for k, v in q.items()},
                "remaining_point_h": round(float(point[i]), 2),
                f"p_leaves_within_{CLEAR_WITHIN_H}h": round(float(p_clear[i]), 3),
            })
        free = berth_free_samples(samples, capacity)
        qs = {f"p{int(q * 100)}": float(np.quantile(free, q)) for q in QUANTILES}
        out["status"] = "free" if len(occupants) < capacity else "occupied"
        out["clearance_h"] = {k: round(v, 2) for k, v in qs.items()}
        out["clearance_time"] = {k: (t + pd.Timedelta(hours=v)).isoformat(timespec="minutes") for k, v in qs.items()}
        out["samples"] = free
        return out
