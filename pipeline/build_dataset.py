"""Step 1 (BE1): raw CSVs -> trusted tables in data/processed/.

Runs the Phase 1 audit (which rebuilds berth visits from port calls), then writes:
  visits.parquet      commercial berth visits used for every model (one row = one stay alongside)
  port_calls.parquet  all-vessel port calls (port, start, end) used only for congestion features
  berths.parquet      berth metadata: port, centroid, polygon, capacity, visit stats
  ports.parquet       ports that have at least one commercial berth

Usage: python -m pipeline.build_dataset
"""
import json

import numpy as np
import pandas as pd

from pipeline.phase1 import berth_audit, profile_csvs
from portpulse.config import COMMERCIAL_TYPES, MIN_CONF, PROCESSED, RAW, REPORTS

PHASE1 = REPORTS / "phase1"


def berth_table(visits: pd.DataFrame) -> pd.DataFrame:
    berths = pd.read_csv(RAW / "berths.csv", sep="|")
    dup = berths["berth"].duplicated(keep=False)
    berths["berth_id"] = berths["berth"].where(~dup, berths["berth"] + "#" + berths["id"].astype(str))
    rings = [berth_audit.read_ewkb(h)[1] for h in berths["geom"]]
    berths["lon"] = [float(np.mean(np.concatenate([r[:-1, 0] for r in rr]))) for rr in rings]
    berths["lat"] = [float(np.mean(np.concatenate([r[:-1, 1] for r in rr]))) for rr in rings]
    # GeoJSON-style outer rings, rounded to ~1 m, for the map.
    berths["polygon"] = [json.dumps([np.round(r, 5).tolist() for r in rr]) for rr in rings]
    berths["area_m2"] = [berth_audit.ring_area_m2(rr) for rr in rings]

    conc = pd.read_csv(PHASE1 / "berth_concurrency_commercial.csv").rename(columns={"berth": "berth_id"})
    berths = berths.merge(conc[["berth_id", "max_concurrent", "share_occupied_time_multi"]], on="berth_id", how="left")
    # A berth whose commercial ships overlap >10% of occupied time is treated as having 2+ slots.
    shared = berths["share_occupied_time_multi"].fillna(0) > 0.10
    berths["capacity"] = np.where(shared, berths["max_concurrent"].fillna(1).clip(lower=2, upper=4), 1).astype(int)

    stats = visits.groupby("berth_id").agg(visits=("visit_id", "size"), median_stay_h=("duration_hours", "median"),
                                           main_type=("vesseltype", lambda s: s.mode().iat[0]))
    berths = berths.merge(stats, on="berth_id", how="inner")
    return berths[["berth_id", "berth", "portid", "portname", "countrycode", "lat", "lon", "area_m2", "capacity",
                   "max_concurrent", "visits", "median_stay_h", "main_type", "polygon"]].rename(columns={"portid": "port_id"})


def main():
    print("Phase 1 profile ...", flush=True)
    profile_csvs.main(RAW, PHASE1)
    print("Phase 1 berth audit ...", flush=True)
    berth_audit.main(RAW, PHASE1)

    mv = pd.read_parquet(PHASE1 / "berth_visits_merged_1h.parquet")
    keep = mv["vesseltype"].isin(COMMERCIAL_TYPES) & (mv["confidence_min"] >= MIN_CONF) & ~mv["flag_year_censored"]
    visits = mv.loc[keep].sort_values(["arrival_time", "vessel_id"]).reset_index(drop=True)
    visits.insert(0, "visit_id", np.arange(len(visits)))
    visits = visits[["visit_id", "vessel_id", "port_id", "berth_id", "vesseltype", "arrival_time", "departure_time",
                     "duration_hours", "n_calls", "confidence_min", "flag_gt_7d"]]
    visits.to_parquet(PROCESSED / "visits.parquet", index=False)

    pc = pd.read_csv(RAW / "portcalls.csv", sep="|", usecols=["mmsi", "port", "ts_start", "ts_end", "conf"],
                     parse_dates=["ts_start", "ts_end"])
    pc = pc[pc["conf"] > 0].drop(columns="conf").rename(columns={"port": "port_id"})
    pc.to_parquet(PROCESSED / "port_calls.parquet", index=False)

    berths = berth_table(visits)
    berths.to_parquet(PROCESSED / "berths.parquet", index=False)

    ports = pd.read_csv(RAW / "ports.csv", sep="|", usecols=["id", "portname", "countryname", "countrycode", "locode"])
    agg = berths.groupby("port_id").agg(n_berths=("berth_id", "size"), visits=("visits", "sum"),
                                        lat=("lat", "mean"), lon=("lon", "mean"))
    ports = ports.rename(columns={"id": "port_id"}).merge(agg, on="port_id", how="inner")
    ports.to_parquet(PROCESSED / "ports.parquet", index=False)

    summary = {"visits": len(visits), "vessels": int(visits["vessel_id"].nunique()), "berths": len(berths),
               "ports": len(ports), "port_calls_for_congestion": len(pc)}
    (PROCESSED / "dataset_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
