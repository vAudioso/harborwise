"""Phase 1 / BE1: can port calls be reconstructed into berth visits?

Checks label semantics (timestamps, duration, conf, edge uncertainty), geometry (CRS,
point-in-berth matching on the full table), same-vessel overlaps, split visits, berth
concurrency and vessel-type join coverage. Writes a candidate berth-visit table with
flags instead of dropping rows.

Usage: python -m pipeline.phase1.berth_audit data/raw reports/phase1
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pandas as pd

M_PER_DEG_LAT = 110_540.0
M_PER_DEG_LON_EQ = 111_320.0
SRID_FLAG = 0x20000000


# --- minimal EWKB reader (shapely is not installed; berth geometries are simple polygons) ---
def _read_geom(buf: bytes, off: int):
    endian = "<" if buf[off] == 1 else ">"
    (gtype,) = struct.unpack_from(endian + "I", buf, off + 1)
    off += 5
    srid = None
    if gtype & SRID_FLAG:
        (srid,) = struct.unpack_from(endian + "I", buf, off)
        off += 4
    gtype &= 0xFF
    if gtype == 1:  # Point
        x, y = struct.unpack_from(endian + "dd", buf, off)
        return ("Point", [(x, y)]), off + 16, srid
    if gtype == 3:  # Polygon -> list of rings
        (nrings,) = struct.unpack_from(endian + "I", buf, off)
        off += 4
        rings = []
        for _ in range(nrings):
            (npts,) = struct.unpack_from(endian + "I", buf, off)
            off += 4
            rings.append(np.frombuffer(buf, dtype=endian + "f8", count=2 * npts, offset=off).reshape(-1, 2))
            off += 16 * npts
        return ("Polygon", rings), off, srid
    if gtype == 2:  # LineString
        (npts,) = struct.unpack_from(endian + "I", buf, off)
        off += 4
        line = np.frombuffer(buf, dtype=endian + "f8", count=2 * npts, offset=off).reshape(-1, 2)
        return ("LineString", [line]), off + 16 * npts, srid
    if gtype in (5, 6):  # MultiLineString / MultiPolygon -> flattened parts
        (nparts,) = struct.unpack_from(endian + "I", buf, off)
        off += 4
        rings = []
        for _ in range(nparts):
            (_, part_rings), off, _ = _read_geom(buf, off)
            rings.extend(part_rings)
        return ("MultiLineString" if gtype == 5 else "MultiPolygon", rings), off, srid
    raise ValueError(f"unsupported WKB type {gtype}")


def read_ewkb(hexstr: str):
    (kind, data), _, srid = _read_geom(bytes.fromhex(hexstr), 0)
    return kind, data, srid


def points_in_rings(px, py, rings):
    """Even-odd ray casting across all rings (handles holes and multipart polygons)."""
    inside = np.zeros(px.shape, dtype=bool)
    for ring in rings:
        x, y = ring[:, 0], ring[:, 1]
        x0, y0, x1, y1 = x[:-1], y[:-1], x[1:], y[1:]
        for a, b, c, d in zip(x0, y0, x1, y1):
            crosses = ((b > py) != (d > py)) & (px < (c - a) * (py - b) / ((d - b) if d != b else 1e-300) + a)
            inside ^= crosses
    return inside


def dist_to_rings_m(px, py, rings):
    """Approximate distance in metres from points to polygon boundary (equirectangular)."""
    k = np.cos(np.radians(np.mean(py))) * M_PER_DEG_LON_EQ
    X, Y = px * k, py * M_PER_DEG_LAT
    best = np.full(px.shape, np.inf)
    for ring in rings:
        sx, sy = ring[:, 0] * k, ring[:, 1] * M_PER_DEG_LAT
        ax, ay, bx, by = sx[:-1], sy[:-1], sx[1:], sy[1:]
        for a, b, c, d in zip(ax, ay, bx, by):
            dx, dy = c - a, d - b
            L = dx * dx + dy * dy
            t = np.clip(((X - a) * dx + (Y - b) * dy) / L, 0, 1) if L > 0 else 0.0
            best = np.minimum(best, np.hypot(X - (a + t * dx), Y - (b + t * dy)))
    return best


def ring_area_m2(rings):
    lat = np.mean(rings[0][:, 1])
    k = np.cos(np.radians(lat)) * M_PER_DEG_LON_EQ
    total = 0.0
    for r in rings:
        x, y = r[:, 0] * k, r[:, 1] * M_PER_DEG_LAT
        total += 0.5 * (np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1]))
    return abs(total)


def concurrency(starts, ends):
    """Max simultaneous visits and share of occupied time with >=2 vessels."""
    t = np.concatenate([starts, ends])
    e = np.concatenate([np.ones(len(starts), int), -np.ones(len(ends), int)])
    order = np.lexsort((e, t))  # ends (-1) before starts (+1) at the same instant
    t, e = t[order], e[order]
    level = np.cumsum(e)
    dt = np.diff(t).astype("timedelta64[s]").astype(float)
    lv = level[:-1]
    occupied = dt[lv >= 1].sum()
    multi = dt[lv >= 2].sum()
    return int(level.max()), (multi / occupied if occupied > 0 else 0.0), occupied


def pct(x):
    return round(100 * float(x), 2)


def main(data_dir=None, out_dir=None):
    data_dir = Path(data_dir or sys.argv[1])
    out_dir = Path(out_dir or sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    R = {}

    pc = pd.read_csv(data_dir / "portcalls.csv", sep="|", low_memory=False)
    ports = pd.read_csv(data_dir / "ports.csv", sep="|")
    berths = pd.read_csv(data_dir / "berths.csv", sep="|")
    vt_o = pd.read_csv(data_dir / "vesseltype_original.csv", sep="|")
    vt_e = pd.read_csv(data_dir / "vesseltype_enriched.csv", sep="|")
    n = len(pc)
    R["rows"] = n

    # ---------------- 1. timestamps and duration ----------------
    pc["ts_start"] = pd.to_datetime(pc["ts_start"])
    pc["ts_end"] = pd.to_datetime(pc["ts_end"])
    diff_s = (pc["ts_end"] - pc["ts_start"]).dt.total_seconds()
    mismatch = (diff_s - pc["duration"]).abs()
    hours = pc["duration"] / 3600
    R["timestamps"] = {
        "end_before_start": int((diff_s < 0).sum()),
        "duration_mismatch_gt_1s": int((mismatch > 1).sum()),
        "duration_mismatch_max_s": float(mismatch.max()),
        "zero_duration": int((pc["duration"] == 0).sum()),
        "duration_lt_10min": int((pc["duration"] < 600).sum()),
        "duration_gt_7d": int((hours > 24 * 7).sum()),
        "duration_gt_30d": int((hours > 24 * 30).sum()),
        "duration_hours_quantiles": {str(q): round(float(hours.quantile(q)), 2) for q in [0.1, 0.25, 0.5, 0.75, 0.9, 0.99]},
        "starts_on_jan1_first_hour": int((pc["ts_start"] < "2019-01-01 01:00").sum()),
        "ends_on_dec31_last_hour": int((pc["ts_end"] > "2019-12-31 23:00").sum()),
        "start_hour_utc_counts": pc["ts_start"].dt.hour.value_counts().sort_index().tolist(),
    }

    # Edge uncertainty: time_bef / time_aft = gap to nearest message outside the call.
    R["edge_uncertainty"] = {
        "time_bef_missing_pct": pct(pc["time_bef"].isna().mean()),
        "time_aft_missing_pct": pct(pc["time_aft"].isna().mean()),
        "time_bef_gt_1h_pct": pct((pc["time_bef"] > 3600).mean()),
        "time_aft_gt_1h_pct": pct((pc["time_aft"] > 3600).mean()),
        "time_aft_missing_by_month_pct": pc.groupby(pc["ts_end"].dt.month)["time_aft"].apply(lambda s: pct(s.isna().mean())).to_dict(),
    }
    conf_bins = pd.cut(pc["conf"], [-0.01, 0, 0.5, 0.9, 0.99, 1.0], labels=["0", "(0,0.5]", "(0.5,0.9]", "(0.9,0.99]", "(0.99,1]"])
    R["conf"] = {
        "distribution": conf_bins.value_counts().sort_index().to_dict(),
        "median_duration_h_by_bin": hours.groupby(conf_bins, observed=True).median().round(2).to_dict(),
        "nb_mes_zero_by_bin": (pc["nb_mes"] == 0).groupby(conf_bins, observed=True).sum().to_dict(),
        "coords_missing_pct_by_bin": pc["latitude"].isna().groupby(conf_bins, observed=True).mean().mul(100).round(2).to_dict(),
    }
    R["coords"] = {
        "missing_pct": pct(pc["latitude"].isna().mean()),
        "missing_when_nb_mes_0_pct": pct(pc.loc[pc["nb_mes"] == 0, "latitude"].isna().mean()),
        "missing_when_nb_mes_gt_0_pct": pct(pc.loc[pc["nb_mes"] > 0, "latitude"].isna().mean()),
    }

    # ---------------- 2. CRS and geometry consistency ----------------
    srids_pc = {read_ewkb(h)[2] for h in pc["geom"].dropna().sample(2000, random_state=0)}
    berth_geoms = [read_ewkb(h) for h in berths["geom"]]
    srids_b = {g[2] for g in berth_geoms}
    srids_p = {read_ewkb(h)[2] for h in ports["geom"].dropna()}
    samp = pc.dropna(subset=["geom"]).sample(5000, random_state=0)
    xy = np.array([read_ewkb(h)[1][0] for h in samp["geom"]])
    geom_vs_latlon = np.abs(xy - samp[["longitude", "latitude"]].to_numpy()).max()
    R["crs"] = {
        "portcalls_srid": sorted(srids_pc), "berths_srid": sorted(srids_b), "ports_srid": sorted(srids_p),
        "portcall_geom_vs_latlon_max_abs_diff_deg": float(geom_vs_latlon),
        "berth_geom_kinds": pd.Series([g[0] for g in berth_geoms]).value_counts().to_dict(),
    }

    # ---------------- 3. joins and port coverage ----------------
    R["joins"] = {
        "portcall_port_not_in_ports": int((~pc["port"].isin(ports["id"])).sum()),
        "ports_total": len(ports),
        "ports_with_calls": int(pc["port"].nunique()),
        "ports_with_berths": int(berths["portid"].nunique()),
        "calls_at_ports_with_berths_pct": pct(pc["port"].isin(berths["portid"]).mean()),
        "duplicate_berth_codes": berths.loc[berths["berth"].duplicated(keep=False), "berth"].unique().tolist(),
        "fully_duplicate_berth_rows_excl_id": int(berths.drop(columns="id").duplicated().sum()),
        "berth_portname_mismatch_with_ports": int((berths.merge(ports[["id", "portname"]], left_on="portid", right_on="id", suffixes=("", "_p"))
                                                   .eval("portname != portname_p")).sum()),
    }
    vt_both = vt_o.merge(vt_e, on="mmsi", suffixes=("_o", "_e"))
    vt = pd.concat([vt_o[["mmsi", "vesseltype"]].assign(vt_source="original"),
                    vt_e.loc[~vt_e["mmsi"].isin(vt_o["mmsi"]), ["mmsi", "vesseltype"]].assign(vt_source="enriched")])
    R["vessel_type"] = {
        "mmsi_in_both_tables": len(vt_both),
        "conflicting_types_in_both": int((vt_both["vesseltype_o"] != vt_both["vesseltype_e"]).sum()),
        "vessels_with_type_pct": pct(pd.Series(pc["mmsi"].unique()).isin(vt["mmsi"]).mean()),
        "calls_with_type_original_pct": pct(pc["mmsi"].isin(vt_o["mmsi"]).mean()),
        "calls_with_type_any_pct": pct(pc["mmsi"].isin(vt["mmsi"]).mean()),
        "join_row_explosion": int(len(pc.merge(vt, on="mmsi", how="left")) - n),
        "invalid_mmsi_not_9_digits": int((~pc["mmsi"].between(100_000_000, 999_999_999)).sum()),
    }

    # ---------------- 4. point-in-berth on the full table ----------------
    # 11 berth codes are reused by two different polygons, so key berths by code plus row id where needed.
    dup = berths["berth"].duplicated(keep=False)
    berths["berth_key"] = berths["berth"].where(~dup, berths["berth"] + "#" + berths["id"].astype(str))
    berths["rings"] = [g[1] for g in berth_geoms]
    berths["area_m2"] = berths["rings"].map(ring_area_m2)
    pc["berth"] = pd.Series(pd.NA, index=pc.index, dtype="string")
    pc["n_berth_hits"] = 0
    pc["dist_nearest_berth_m"] = np.nan
    has_xy = pc["latitude"].notna()
    for port_id, bgrp in berths.groupby("portid"):
        idx = pc.index[has_xy & (pc["port"] == port_id)]
        if len(idx) == 0:
            continue
        px = pc.loc[idx, "longitude"].to_numpy()
        py = pc.loc[idx, "latitude"].to_numpy()
        hits = np.zeros(len(idx), int)
        first = np.full(len(idx), None, dtype=object)
        dmin = np.full(len(idx), np.inf)
        for code, rings in zip(bgrp["berth_key"], bgrp["rings"]):
            allx = np.concatenate([r[:, 0] for r in rings]); ally = np.concatenate([r[:, 1] for r in rings])
            pad = 0.01  # ~1 km bbox prefilter for distance
            near = (px > allx.min() - pad) & (px < allx.max() + pad) & (py > ally.min() - pad) & (py < ally.max() + pad)
            if not near.any():
                continue
            ins = np.zeros(len(idx), bool)
            ins[near] = points_in_rings(px[near], py[near], rings)
            first[ins & (hits == 0)] = code
            hits += ins
            d = np.full(len(idx), np.inf)
            d[near] = dist_to_rings_m(px[near], py[near], rings)
            d[ins] = 0.0
            dmin = np.minimum(dmin, d)
        pc.loc[idx, "berth"] = pd.array(first, dtype="string")
        pc.loc[idx, "n_berth_hits"] = hits
        pc.loc[idx, "dist_nearest_berth_m"] = np.where(np.isfinite(dmin), dmin, np.nan)

    at_berth_port = pc["port"].isin(berths["portid"])
    cand = has_xy & at_berth_port
    matched = pc["berth"].notna()
    unmatched_d = pc.loc[cand & ~matched, "dist_nearest_berth_m"]
    counts = pc.loc[matched, "berth"].value_counts()
    bcmp = berths.set_index("berth_key")[["number"]].join(counts.rename("matched_calls"), how="left").fillna(0)
    R["berth_match"] = {
        "all_calls": n,
        "calls_with_coords": int(has_xy.sum()),
        "calls_with_coords_at_ports_with_berths": int(cand.sum()),
        "matched_calls": int(matched.sum()),
        "match_rate_among_candidates_pct": pct(matched.sum() / cand.sum()),
        "match_rate_among_all_calls_pct": pct(matched.sum() / n),
        "matched_in_more_than_one_berth": int((pc["n_berth_hits"] > 1).sum()),
        "unmatched_within_50m": int((unmatched_d <= 50).sum()),
        "unmatched_within_200m": int((unmatched_d <= 200).sum()),
        "unmatched_beyond_1km_or_no_berth_near": int((unmatched_d.isna() | (unmatched_d > 1000)).sum()),
        "match_rate_by_conf_bin_pct": matched[cand].groupby(conf_bins[cand], observed=True).mean().mul(100).round(2).to_dict(),
        "our_counts_vs_published_number_corr": round(float(np.corrcoef(bcmp["number"], bcmp["matched_calls"])[0, 1]), 4),
        "our_counts_vs_published_number_ratio_median": round(float((bcmp["matched_calls"] / bcmp["number"].replace(0, np.nan)).median()), 3),
        "berth_area_m2_quantiles": {str(q): round(float(berths["area_m2"].quantile(q))) for q in [0.1, 0.5, 0.9, 0.99]},
    }

    # ---------------- 5. same-vessel overlaps and split visits ----------------
    pc = pc.sort_values(["mmsi", "ts_start", "ts_end"]).reset_index(drop=True)
    same_v = pc["mmsi"].eq(pc["mmsi"].shift())
    prev_end = pc["ts_end"].shift()
    overlap = same_v & (pc["ts_start"] < prev_end)
    gap_h = (pc["ts_start"] - prev_end).dt.total_seconds() / 3600
    same_port = same_v & pc["port"].eq(pc["port"].shift())
    same_berth = same_port & pc["berth"].notna() & pc["berth"].eq(pc["berth"].shift()).fillna(False)
    g = gap_h[same_port & ~overlap]
    R["vessel_sequences"] = {
        "overlapping_calls_same_vessel": int(overlap.sum()),
        "overlapping_calls_same_vessel_different_port": int((overlap & ~same_port).sum()),
        "consecutive_same_port_pairs": int(same_port.sum()),
        "same_port_gap_lt_1h": int((g < 1).sum()),
        "same_port_gap_lt_3h": int((g < 3).sum()),
        "same_port_gap_lt_6h": int((g < 6).sum()),
        "same_port_gap_hours_quantiles": {str(q): round(float(g.quantile(q)), 2) for q in [0.05, 0.1, 0.25, 0.5]},
        "same_berth_gap_lt_1h": int((gap_h[same_berth & ~overlap] < 1).sum()),
        "same_port_gap_lt_1h_but_different_berth": int(((gap_h < 1) & same_port & ~overlap & pc["berth"].notna()
                                                        & pc["berth"].shift().notna() & ~same_berth).sum()),
    }

    # ---------------- 6. berth concurrency (is a polygon one slot or a zone?) ----------------
    rows = []
    for code, grp in pc[pc["berth"].notna()].groupby("berth"):
        if len(grp) < 5:
            continue
        mx, multi_share, occ = concurrency(grp["ts_start"].to_numpy(), grp["ts_end"].to_numpy())
        rows.append((code, len(grp), mx, multi_share, occ / (365 * 86400)))
    conc = pd.DataFrame(rows, columns=["berth", "calls", "max_concurrent", "share_occupied_time_multi", "occupancy_ratio"])
    conc = conc.merge(berths[["berth_key", "area_m2"]].rename(columns={"berth_key": "berth"}), on="berth", how="left")
    conc.to_csv(out_dir / "berth_concurrency.csv", index=False)
    R["berth_concurrency"] = {
        "berths_analysed": len(conc),
        "max_concurrent_quantiles": {str(q): float(conc["max_concurrent"].quantile(q)) for q in [0.25, 0.5, 0.75, 0.9]},
        "berths_never_shared": int((conc["max_concurrent"] == 1).sum()),
        "berths_shared_gt_10pct_of_occupied_time": int((conc["share_occupied_time_multi"] > 0.10).sum()),
        "berths_shared_gt_50pct_of_occupied_time": int((conc["share_occupied_time_multi"] > 0.50).sum()),
        "corr_area_vs_max_concurrent": round(float(np.corrcoef(np.log1p(conc["area_m2"]), conc["max_concurrent"])[0, 1]), 3),
        "occupancy_ratio_median": round(float(conc["occupancy_ratio"].median()), 3),
    }

    # ---------------- 7. candidate berth-visit table (flag, don't drop) ----------------
    pc = pc.merge(vt, on="mmsi", how="left")
    pc["flag_zero_duration"] = pc["duration"] == 0
    pc["flag_gt_7d"] = pc["duration"] > 7 * 86400
    pc["flag_low_conf"] = pc["conf"] < 0.5
    pc["flag_edge_uncertain_gt_1h"] = (pc["time_bef"] > 3600) | (pc["time_aft"] > 3600)
    pc["flag_year_censored"] = (pc["ts_start"] < "2019-01-01 01:00") | (pc["ts_end"] > "2019-12-31 23:00")
    pc["flag_overlap_prev"] = overlap.to_numpy()
    pc["flag_split_candidate"] = (same_port & ~overlap & (gap_h < 1)).to_numpy()
    visits = pc.loc[pc["berth"].notna()].rename(columns={
        "id": "portcall_id", "mmsi": "vessel_id", "port": "port_id", "berth": "berth_id",
        "ts_start": "arrival_time", "ts_end": "departure_time", "conf": "confidence"})
    visits["duration_hours"] = visits["duration"] / 3600
    keep = ["portcall_id", "vessel_id", "port_id", "berth_id", "arrival_time", "departure_time", "duration_hours",
            "vesseltype", "vt_source", "confidence", "nb_mes", "time_bef", "time_aft", "n_berth_hits"] + \
           [c for c in visits.columns if c.startswith("flag_")]
    visits = visits[keep]
    clean = ~(visits["flag_zero_duration"] | visits["flag_overlap_prev"] | visits["flag_low_conf"])
    R["candidate_table"] = {
        "rows": len(visits),
        "rows_without_blocking_flags": int(clean.sum()),
        "flag_counts": {c: int(visits[c].sum()) for c in visits.columns if c.startswith("flag_")},
        "berths_with_ge_100_clean_visits": int((visits.loc[clean, "berth_id"].value_counts() >= 100).sum()),
        "berths_with_ge_500_clean_visits": int((visits.loc[clean, "berth_id"].value_counts() >= 500).sum()),
        "clean_duration_hours_quantiles": {str(q): round(float(visits.loc[clean, "duration_hours"].quantile(q)), 2) for q in [0.1, 0.25, 0.5, 0.75, 0.9]},
        "clean_with_vessel_type_pct": pct(visits.loc[clean, "vesseltype"].notna().mean()),
        "clean_by_month": visits.loc[clean, "arrival_time"].dt.month.value_counts().sort_index().to_dict(),
    }
    visits.to_parquet(out_dir / "berth_visits_candidate.parquet", index=False)

    # ---------------- 8. merge split calls into berth visits ----------------
    # A call starts/ends when speed crosses 0.5 kn, so one stay alongside can be cut into
    # several calls. Merge consecutive calls of the same vessel at the same berth when the
    # gap is short. pc is still sorted by mmsi, ts_start (the left merge keeps order).
    gap = gap_h.to_numpy()
    sb = same_berth.to_numpy() & ~overlap.to_numpy()
    R["same_berth_gap_hours_quantiles"] = {str(q): round(float(np.nanquantile(gap[sb], q)), 2) for q in [0.1, 0.25, 0.5, 0.75, 0.9]}
    commercial = {"tank", "cont", "bulk", "gcar", "crui"}
    pc["is_commercial"] = pc["vesseltype"].isin(commercial)
    m = pc["berth"].notna()
    merge_sim = {}
    merged_by_thr = {}
    for thr in [0.5, 1, 2, 3]:
        new_visit = ~(sb & (gap < thr))
        vid = np.cumsum(new_visit)
        agg = (pc.loc[m].assign(visit=vid[m.to_numpy()])
               .groupby("visit")
               .agg(vessel_id=("mmsi", "first"), port_id=("port", "first"), berth_id=("berth", "first"),
                    arrival_time=("ts_start", "min"), departure_time=("ts_end", "max"), n_calls=("id", "size"),
                    stopped_hours=("duration", lambda s: s.sum() / 3600), confidence_min=("conf", "min"),
                    vesseltype=("vesseltype", "first"), vt_source=("vt_source", "first"),
                    is_commercial=("is_commercial", "first")))
        agg["duration_hours"] = (agg["departure_time"] - agg["arrival_time"]).dt.total_seconds() / 3600
        merged_by_thr[thr] = agg
        merge_sim[str(thr)] = {
            "visits": len(agg),
            "commercial_visits": int(agg["is_commercial"].sum()),
            "median_duration_h_all": round(float(agg["duration_hours"].median()), 2),
            "median_duration_h_commercial": round(float(agg.loc[agg["is_commercial"], "duration_hours"].median()), 2),
            "commercial_visits_multi_call_pct": pct((agg.loc[agg["is_commercial"], "n_calls"] > 1).mean()),
        }
    R["merge_simulation"] = merge_sim

    # Chosen threshold: 1 h (see report). Commercial cargo/passenger ships are the HarborWise target.
    mv = merged_by_thr[1].reset_index(drop=True)
    mv["flag_low_conf"] = mv["confidence_min"] < 0.5
    mv["flag_gt_7d"] = mv["duration_hours"] > 24 * 7
    mv["flag_year_censored"] = (mv["arrival_time"] < "2019-01-01 01:00") | (mv["departure_time"] > "2019-12-31 23:00")
    mv.to_parquet(out_dir / "berth_visits_merged_1h.parquet", index=False)

    com = mv[mv["is_commercial"] & ~mv["flag_low_conf"]]
    rows = []
    for code, grp in com.groupby("berth_id"):
        if len(grp) < 5:
            continue
        mx, multi_share, occ = concurrency(grp["arrival_time"].to_numpy(), grp["departure_time"].to_numpy())
        rows.append((code, len(grp), mx, multi_share))
    cconc = pd.DataFrame(rows, columns=["berth", "visits", "max_concurrent", "share_occupied_time_multi"])
    cconc.to_csv(out_dir / "berth_concurrency_commercial.csv", index=False)
    vc = com["berth_id"].value_counts()
    R["commercial_subset"] = {
        "visits": len(com),
        "vessels": int(com["vessel_id"].nunique()),
        "by_type": com["vesseltype"].value_counts().to_dict(),
        "ports": int(com["port_id"].nunique()),
        "berths": int(com["berth_id"].nunique()),
        "berths_with_ge_50_visits": int((vc >= 50).sum()),
        "berths_with_ge_100_visits": int((vc >= 100).sum()),
        "share_of_visits_at_berths_ge_100_pct": pct(vc[vc >= 100].sum() / vc.sum()),
        "duration_hours_quantiles": {str(q): round(float(com["duration_hours"].quantile(q)), 2) for q in [0.1, 0.25, 0.5, 0.75, 0.9, 0.99]},
        "median_duration_h_by_type": com.groupby("vesseltype")["duration_hours"].median().round(2).to_dict(),
        "visits_by_month": com["arrival_time"].dt.month.value_counts().sort_index().to_dict(),
        "concurrency_berths_analysed": len(cconc),
        "concurrency_never_shared": int((cconc["max_concurrent"] == 1).sum()),
        "concurrency_shared_gt_10pct_time": int((cconc["share_occupied_time_multi"] > 0.10).sum()),
        "concurrency_max_quantiles": {str(q): float(cconc["max_concurrent"].quantile(q)) for q in [0.25, 0.5, 0.75, 0.9]},
    }

    (out_dir / "berth_audit.json").write_text(json.dumps(R, indent=2, default=str))


if __name__ == "__main__":
    main()
