"""Checkpoint dataset, leakage-safe context features and the sklearn feature transformer.

A checkpoint row is "visit v, observed at time t = arrival + k hours, still alongside".
The label is remaining_h = departure - t. Every feature must be computable from what is
observable at t; FEATURE_DOCS records why each one is.
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from harborwise.config import CHECKPOINTS_H, COMMERCIAL_TYPES, TRAIN_END, VAL_END

H = np.timedelta64(1, "h")
VT_CODE = {t: i for i, t in enumerate(COMMERCIAL_TYPES)}

FEATURE_DOCS = {
    "elapsed_h": "Hours since this ship stopped alongside; observed directly.",
    "hour": "Hour of day (UTC) at prediction time.",
    "weekday": "Day of week at prediction time.",
    "month": "Month at prediction time.",
    "hurricane_season": "1 if June–November at prediction time.",
    "arrival_hour": "Hour the ship stopped alongside; in the past at prediction time.",
    "vt_code": "Vessel type from the registry; static.",
    "port_occupancy": "Other commercial ships alongside in the port at t (arrived <= t, not yet left at t).",
    "berth_occupancy_others": "Other commercial ships alongside at the same berth at t.",
    "port_arrivals_24h_all": "All-vessel calls (incl. tugs/service craft) that started in the port in (t-24h, t].",
    "port_departures_24h_comm": "Commercial ships that left the port in (t-24h, t].",
    "port_arrivals_7d_comm": "Commercial ships that arrived in the port in (t-7d, t].",
    "vessel_prev_visits": "Earlier 2019 visits by this ship (all ended before this arrival).",
    "vessel_prev_mean_log_stay": "Mean log1p stay of those earlier visits.",
    "vessel_prev_visits_port": "Earlier visits by this ship to this port.",
    "vessel_prev_mean_log_stay_port": "Mean log1p stay of earlier visits to this port.",
    "vessel_last_stay_port_h": "Length of this ship's previous stay in this port (ended before this arrival).",
    "vessel_median_stay_port_h": "Median of this ship's earlier stays in this port.",
    "hours_since_last_visit_port": "Hours since this ship last left this port (liner rotation).",
    "vessel_prev_visits_berth": "Earlier visits by this ship to this berth.",
    "vessel_median_stay_berth_h": "Median of this ship's earlier stays at this berth.",
    "vessel_max_prev_stay_h": "Longest earlier 2019 stay by this ship (flags ships prone to lay-ups).",
    "svc_arrivals_berth_1h": "Harbour craft (tugs, pilots, barges) that stopped at this berth in (t-1h, t].",
    "svc_arrivals_berth_3h": "Harbour craft that stopped at this berth in (t-3h, t].",
    "svc_alongside_berth_now": "Harbour craft stopped at this berth at t (started <= t, not yet left).",
    "svc_arrivals_berth_since_arrival": "Harbour craft stops at this berth since this ship arrived.",
    "med_total_berth_type": "Training-period median stay at this berth for this vessel type (fitted on train only).",
    "med_total_berth": "Training-period median stay at this berth (train only).",
    "med_total_port": "Training-period median stay in this port (train only).",
    "med_remaining_cp": "Training-period median remaining time at this berth/port/type for this elapsed time (train only).",
    "log_berth_train_visits": "log1p of training-period visits at this berth (train only).",
    "q90_total_berth": "Training-period 90th percentile stay at this berth (train only).",
    "share_long_stays_berth": "Training-period share of stays over 72 h at this berth (train only).",
}

BASE_COLS = ["elapsed_h", "hour", "weekday", "month", "hurricane_season", "arrival_hour", "vt_code"]
CONTEXT_COLS = ["port_occupancy", "berth_occupancy_others", "port_arrivals_24h_all", "port_departures_24h_comm",
                "port_arrivals_7d_comm", "vessel_prev_visits", "vessel_prev_mean_log_stay",
                "vessel_prev_visits_port", "vessel_prev_mean_log_stay_port", "vessel_last_stay_port_h",
                "vessel_median_stay_port_h", "hours_since_last_visit_port", "vessel_prev_visits_berth",
                "vessel_median_stay_berth_h", "vessel_max_prev_stay_h", "svc_arrivals_berth_1h", "svc_arrivals_berth_3h",
                "svc_alongside_berth_now", "svc_arrivals_berth_since_arrival"]
STAT_COLS = ["med_total_berth_type", "med_total_berth", "med_total_port", "med_remaining_cp", "log_berth_train_visits",
             "q90_total_berth", "share_long_stays_berth"]
RAW_KEYS = ["berth_id", "port_id", "vesseltype"]


def _ns(s) -> np.ndarray:
    return pd.to_datetime(s).to_numpy(dtype="datetime64[ns]").astype(np.int64)


class _WindowIndex:
    """Event times grouped by key and sorted once, so window counts are just two binary searches."""

    def __init__(self, keys, times):
        order = np.argsort(keys, kind="stable")
        kt, tt = keys[order], times[order]
        uniq, starts = np.unique(kt, return_index=True)
        ends = np.append(starts[1:], len(kt))
        self.groups = {k: np.sort(tt[s:e]) for k, s, e in zip(uniq.tolist(), starts, ends)}

    def count(self, keys_q, t_lo, t_hi):
        """For each query i, count events with key == keys_q[i] and t_lo[i] < time <= t_hi[i]."""
        out = np.zeros(len(keys_q), dtype=np.int64)
        for k in np.unique(keys_q).tolist():
            arr = self.groups.get(k)
            if arr is None:
                continue
            sel = np.nonzero(keys_q == k)[0]
            out[sel] = np.searchsorted(arr, t_hi[sel], side="right") - np.searchsorted(arr, t_lo[sel], side="right")
        return out


class ContextIndex:
    """Sorted event indexes for the congestion and harbour-craft features. Build once and reuse it
    (the API does) instead of re-sorting 1.3 M port calls for every prediction."""

    def __init__(self, visits: pd.DataFrame, port_calls: pd.DataFrame, service_stops: pd.DataFrame | None = None):
        v_port, v_berth = visits["port_id"].to_numpy(), visits["berth_id"].astype(str).to_numpy()
        v_arr, v_dep = _ns(visits["arrival_time"]), _ns(visits["departure_time"])
        self.port_arr, self.port_dep = _WindowIndex(v_port, v_arr), _WindowIndex(v_port, v_dep)
        self.berth_arr, self.berth_dep = _WindowIndex(v_berth, v_arr), _WindowIndex(v_berth, v_dep)
        self.calls = _WindowIndex(port_calls["port_id"].to_numpy(), _ns(port_calls["ts_start"]))
        self.svc_start = self.svc_end = None
        if service_stops is not None and len(service_stops):
            s_berth = service_stops["berth_id"].astype(str).to_numpy()
            self.svc_start = _WindowIndex(s_berth, _ns(service_stops["start"]))
            self.svc_end = _WindowIndex(s_berth, _ns(service_stops["end"]))


def context_features(points: pd.DataFrame, visits: pd.DataFrame, port_calls: pd.DataFrame,
                     self_in_table: np.ndarray, service_stops: pd.DataFrame | None = None,
                     index: ContextIndex | None = None) -> pd.DataFrame:
    """Congestion and harbour-craft features at each point's time t. points needs port_id, berth_id, t, arrival_time."""
    ix = index or ContextIndex(visits, port_calls, service_stops)
    t = _ns(points["t"])
    lo_inf = np.full(len(t), np.iinfo(np.int64).min)
    day, week, hour = int(24 * 3600 * 1e9), int(7 * 24 * 3600 * 1e9), int(3600 * 1e9)
    q_port, q_berth = points["port_id"].to_numpy(), points["berth_id"].astype(str).to_numpy()
    selfc = self_in_table.astype(int)

    # Alongside at t  <=>  arrived <= t and departed > t  ==  (#arrived <= t) - (#departed <= t)
    port_occ = ix.port_arr.count(q_port, lo_inf, t) - ix.port_dep.count(q_port, lo_inf, t) - selfc
    berth_occ = ix.berth_arr.count(q_berth, lo_inf, t) - ix.berth_dep.count(q_berth, lo_inf, t) - selfc
    out = {
        "port_occupancy": np.clip(port_occ, 0, None),
        "berth_occupancy_others": np.clip(berth_occ, 0, None),
        "port_arrivals_24h_all": ix.calls.count(q_port, t - day, t),
        "port_departures_24h_comm": ix.port_dep.count(q_port, t - day, t),
        "port_arrivals_7d_comm": ix.port_arr.count(q_port, t - week, t),
    }
    # Tugs, pilots, bunker barges and other harbour craft stopping at the same berth. Tugs and
    # pilots typically arrive shortly before a ship sails, so recent arrivals signal departure.
    if ix.svc_start is not None:
        arr = _ns(points["arrival_time"])
        out["svc_arrivals_berth_1h"] = ix.svc_start.count(q_berth, t - hour, t)
        out["svc_arrivals_berth_3h"] = ix.svc_start.count(q_berth, t - 3 * hour, t)
        out["svc_alongside_berth_now"] = np.clip(ix.svc_start.count(q_berth, lo_inf, t) - ix.svc_end.count(q_berth, lo_inf, t), 0, None)
        out["svc_arrivals_berth_since_arrival"] = ix.svc_start.count(q_berth, arr, t)
    return pd.DataFrame(out, index=points.index)


def _prior_median(v: pd.DataFrame, keys: list) -> pd.Series:
    """Median stay of each group's earlier rows (rows sorted by arrival within the group)."""
    med = v.groupby(keys, sort=False)["duration_hours"].expanding().median()
    med = med.reset_index(level=list(range(len(keys))), drop=True).reindex(v.index)
    return med.groupby([v[k] for k in keys], sort=False).shift()


def vessel_history(visits: pd.DataFrame) -> pd.DataFrame:
    """Per visit: stats of the same ship's earlier visits that ended before this arrival.

    Liner services (container, cruise) repeat the same port/berth on a schedule, so the ship's
    own previous stays at this port and berth are the strongest signals available at arrival.
    """
    v = visits[["visit_id", "vessel_id", "port_id", "berth_id", "arrival_time", "departure_time", "duration_hours"]].copy()
    v = v.sort_values(["vessel_id", "arrival_time"])
    v["log_stay"] = np.log1p(v["duration_hours"])
    out = pd.DataFrame(index=v.index)
    for suffix, keys in (("", ["vessel_id"]), ("_port", ["vessel_id", "port_id"])):
        g = v.groupby(keys, sort=False)
        n_prev = g.cumcount()
        csum = g["log_stay"].cumsum() - v["log_stay"]
        out["vessel_prev_visits" + suffix] = n_prev
        out["vessel_prev_mean_log_stay" + suffix] = (csum / n_prev.replace(0, np.nan))
    gp = v.groupby(["vessel_id", "port_id"], sort=False)
    out["vessel_last_stay_port_h"] = gp["duration_hours"].shift()
    out["vessel_median_stay_port_h"] = _prior_median(v, ["vessel_id", "port_id"])
    out["hours_since_last_visit_port"] = (v["arrival_time"] - gp["departure_time"].shift()).dt.total_seconds() / 3600
    gv = v.groupby("vessel_id", sort=False)["duration_hours"]
    out["vessel_max_prev_stay_h"] = gv.cummax().groupby(v["vessel_id"], sort=False).shift()
    gb = v.groupby(["vessel_id", "berth_id"], sort=False)
    out["vessel_prev_visits_berth"] = gb.cumcount()
    out["vessel_median_stay_berth_h"] = _prior_median(v, ["vessel_id", "berth_id"])
    # A ship cannot be alongside twice at once, but MMSI errors exist: drop history whose last
    # visit had not ended by this arrival.
    prev_dep = v.groupby("vessel_id")["departure_time"].shift()
    bad = prev_dep > v["arrival_time"]
    out.loc[bad, [c for c in out.columns]] = np.nan
    out["visit_id"] = v["visit_id"]
    return out.reset_index(drop=True)


def time_features(t: pd.Series, arrival: pd.Series) -> pd.DataFrame:
    t = pd.to_datetime(t)
    return pd.DataFrame({
        "hour": t.dt.hour, "weekday": t.dt.weekday, "month": t.dt.month,
        "hurricane_season": t.dt.month.between(6, 11).astype(int),
        "arrival_hour": pd.to_datetime(arrival).dt.hour,
    }, index=t.index)


def build_checkpoints(visits: pd.DataFrame, port_calls: pd.DataFrame, checkpoints=CHECKPOINTS_H,
                      service_stops: pd.DataFrame | None = None) -> pd.DataFrame:
    """checkpoints=(0,) gives one row per visit at arrival, labelled with the full turnaround time."""
    rows = []
    for cp in checkpoints:
        v = visits[visits["duration_hours"] > cp].copy()
        v["elapsed_h"] = float(cp)
        v["t"] = v["arrival_time"] + pd.to_timedelta(cp, unit="h")
        rows.append(v)
    df = pd.concat(rows, ignore_index=True)
    df["remaining_h"] = (df["departure_time"] - df["t"]).dt.total_seconds() / 3600
    df = pd.concat([df, time_features(df["t"], df["arrival_time"])], axis=1)
    df["vt_code"] = df["vesseltype"].map(VT_CODE)
    df = df.merge(vessel_history(visits), on="visit_id", how="left")
    df = pd.concat([df, context_features(df, visits, port_calls, np.ones(len(df), bool), service_stops)], axis=1)
    df["split"] = assign_split(df)
    return df


def assign_split(df: pd.DataFrame) -> pd.Series:
    """Chronological split on t, purging rows whose label would reach into the next period."""
    t, dep = df["t"], df["departure_time"]
    split = np.select(
        [(t < TRAIN_END) & (dep < TRAIN_END),
         (t >= TRAIN_END) & (t < VAL_END) & (dep < VAL_END),
         t >= VAL_END],
        ["train", "val", "test"], default="purged")
    return pd.Series(split, index=df.index)


def _floor_checkpoint(elapsed: np.ndarray) -> np.ndarray:
    cps = np.array(CHECKPOINTS_H, dtype=float)
    idx = np.clip(np.searchsorted(cps, elapsed, side="right") - 1, 0, len(cps) - 1)
    return cps[idx]


class FeatureBuilder(BaseEstimator, TransformerMixin):
    """Turns a checkpoint frame into the model matrix.

    Historical medians are fitted on the training rows only (fit), then looked up with a
    fallback chain (berth+type -> berth -> port -> type -> global) so unseen berths still work.
    Identifiers (mmsi, berth, port) never enter the matrix as numbers.
    """

    def __init__(self, feature_set: str = "full", min_count: int = 10):
        self.feature_set = feature_set
        self.min_count = min_count

    def _cols(self):
        if self.feature_set == "basic":
            return BASE_COLS
        return BASE_COLS + CONTEXT_COLS + STAT_COLS

    def fit(self, X: pd.DataFrame, y=None):
        y = np.asarray(y, dtype=float)
        d = X[RAW_KEYS + ["elapsed_h"]].copy()
        d["remaining"] = y
        d["total"] = y + d["elapsed_h"]
        d["cp"] = _floor_checkpoint(d["elapsed_h"].to_numpy())
        first = d[d["elapsed_h"] == d["elapsed_h"].min()]  # one row per visit for stay-length stats

        def med(frame, keys, col):
            g = frame.groupby(keys)[col].agg(["median", "size"])
            return g.loc[g["size"] >= self.min_count, "median"]

        self.global_total_ = float(first["total"].median())
        self.total_ = {k: med(first, list(k), "total") for k in
                       [("berth_id", "vesseltype"), ("berth_id",), ("port_id",), ("vesseltype",)]}
        self.remaining_ = {k: med(d, list(k), "remaining") for k in
                           [("berth_id", "cp"), ("port_id", "cp"), ("vesseltype", "cp"), ("cp",)]}
        self.berth_visits_ = first.groupby("berth_id").size()

        def stat(keys, fn):
            g = first.groupby(list(keys))["total"].agg([fn, "size"])
            return g.loc[g["size"] >= self.min_count, g.columns[0]]

        q90 = lambda x: x.quantile(0.9)  # noqa: E731
        q90.__name__ = "q90"
        long = lambda x: (x > 72).mean()  # noqa: E731
        long.__name__ = "long"
        self.q90_ = {k: stat(k, q90) for k in [("berth_id",), ("port_id",), ("vesseltype",)]}
        self.long_ = {k: stat(k, long) for k in [("berth_id",), ("port_id",), ("vesseltype",)]}
        self.global_q90_ = float(first["total"].quantile(0.9))
        self.global_long_ = float((first["total"] > 72).mean())
        self.feature_names_ = self._cols()
        return self

    @staticmethod
    def _lookup(frame, keys, table):
        idx = pd.MultiIndex.from_frame(frame[list(keys)]) if len(keys) > 1 else frame[keys[0]]
        return pd.Series(table.reindex(idx).to_numpy(), index=frame.index)

    def _chain(self, frame, tables, chain, default):
        out = pd.Series(np.nan, index=frame.index)
        for keys in chain:
            out = out.fillna(self._lookup(frame, keys, tables[keys]))
        return out.fillna(default)

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        out = X.reindex(columns=BASE_COLS + CONTEXT_COLS).astype(float)
        if self.feature_set != "basic":
            f = X[RAW_KEYS + ["elapsed_h"]].copy()
            f["cp"] = _floor_checkpoint(f["elapsed_h"].to_numpy())
            t = self.total_
            out["med_total_berth_type"] = self._chain(f, t, [("berth_id", "vesseltype"), ("berth_id",), ("port_id",), ("vesseltype",)], self.global_total_)
            out["med_total_berth"] = self._chain(f, t, [("berth_id",), ("port_id",), ("vesseltype",)], self.global_total_)
            out["med_total_port"] = self._chain(f, t, [("port_id",), ("vesseltype",)], self.global_total_)
            out["med_remaining_cp"] = self._chain(f, self.remaining_, [("berth_id", "cp"), ("port_id", "cp"), ("vesseltype", "cp"), ("cp",)],
                                                  float(np.nanmedian(self.remaining_[("cp",)].to_numpy())))
            out["log_berth_train_visits"] = np.log1p(f["berth_id"].map(self.berth_visits_).fillna(0).to_numpy())
            chain = [("berth_id",), ("port_id",), ("vesseltype",)]
        if self.feature_set != "basic" and hasattr(self, "q90_"):  # models saved before these stats existed skip them
            out["q90_total_berth"] = self._chain(f, self.q90_, chain, self.global_q90_)
            out["share_long_stays_berth"] = self._chain(f, self.long_, chain, self.global_long_)
        return out[self.feature_names_]

    def get_feature_names_out(self, input_features=None):
        return np.array(self.feature_names_)
