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
    "med_total_berth_type": "Training-period median stay at this berth for this vessel type (fitted on train only).",
    "med_total_berth": "Training-period median stay at this berth (train only).",
    "med_total_port": "Training-period median stay in this port (train only).",
    "med_remaining_cp": "Training-period median remaining time at this berth/port/type for this elapsed time (train only).",
    "log_berth_train_visits": "log1p of training-period visits at this berth (train only).",
}

BASE_COLS = ["elapsed_h", "hour", "weekday", "month", "hurricane_season", "arrival_hour", "vt_code"]
CONTEXT_COLS = ["port_occupancy", "berth_occupancy_others", "port_arrivals_24h_all", "port_departures_24h_comm",
                "port_arrivals_7d_comm", "vessel_prev_visits", "vessel_prev_mean_log_stay",
                "vessel_prev_visits_port", "vessel_prev_mean_log_stay_port"]
STAT_COLS = ["med_total_berth_type", "med_total_berth", "med_total_port", "med_remaining_cp", "log_berth_train_visits"]
RAW_KEYS = ["berth_id", "port_id", "vesseltype"]


def _ns(s) -> np.ndarray:
    return pd.to_datetime(s).to_numpy(dtype="datetime64[ns]").astype(np.int64)


def _count_in_window(keys_tbl, times_tbl, keys_q, t_lo, t_hi):
    """For each query i, count table rows with key == keys_q[i] and t_lo[i] < time <= t_hi[i]."""
    out = np.zeros(len(keys_q), dtype=np.int64)
    order = np.argsort(keys_tbl, kind="stable")
    kt, tt = keys_tbl[order], times_tbl[order]
    uniq, starts = np.unique(kt, return_index=True)
    ends = np.append(starts[1:], len(kt))
    for k, s, e in zip(uniq, starts, ends):
        sel = np.nonzero(keys_q == k)[0]
        if len(sel) == 0:
            continue
        arr = np.sort(tt[s:e])
        out[sel] = np.searchsorted(arr, t_hi[sel], side="right") - np.searchsorted(arr, t_lo[sel], side="right")
    return out


def context_features(points: pd.DataFrame, visits: pd.DataFrame, port_calls: pd.DataFrame,
                     self_in_table: np.ndarray) -> pd.DataFrame:
    """Congestion features at each point's time t. points needs port_id, berth_id, t."""
    t = _ns(points["t"])
    lo_inf = np.full(len(t), np.iinfo(np.int64).min)
    day, week = int(24 * 3600 * 1e9), int(7 * 24 * 3600 * 1e9)
    v_port, v_berth = visits["port_id"].to_numpy(), visits["berth_id"].astype(str).to_numpy()
    v_arr, v_dep = _ns(visits["arrival_time"]), _ns(visits["departure_time"])
    q_port, q_berth = points["port_id"].to_numpy(), points["berth_id"].astype(str).to_numpy()
    selfc = self_in_table.astype(int)

    # Alongside at t  <=>  arrived <= t and departed > t  ==  (#arrived <= t) - (#departed <= t)
    port_occ = (_count_in_window(v_port, v_arr, q_port, lo_inf, t)
                - _count_in_window(v_port, v_dep, q_port, lo_inf, t)) - selfc
    berth_occ = (_count_in_window(v_berth, v_arr, q_berth, lo_inf, t)
                 - _count_in_window(v_berth, v_dep, q_berth, lo_inf, t)) - selfc
    return pd.DataFrame({
        "port_occupancy": np.clip(port_occ, 0, None),
        "berth_occupancy_others": np.clip(berth_occ, 0, None),
        "port_arrivals_24h_all": _count_in_window(port_calls["port_id"].to_numpy(), _ns(port_calls["ts_start"]),
                                                  q_port, t - day, t),
        "port_departures_24h_comm": _count_in_window(v_port, v_dep, q_port, t - day, t),
        "port_arrivals_7d_comm": _count_in_window(v_port, v_arr, q_port, t - week, t),
    }, index=points.index)


def vessel_history(visits: pd.DataFrame) -> pd.DataFrame:
    """Per visit: stats of the same ship's earlier visits that ended before this arrival."""
    v = visits[["visit_id", "vessel_id", "port_id", "arrival_time", "departure_time", "duration_hours"]].copy()
    v = v.sort_values(["vessel_id", "arrival_time"])
    v["log_stay"] = np.log1p(v["duration_hours"])
    out = pd.DataFrame(index=v.index)
    for suffix, keys in (("", ["vessel_id"]), ("_port", ["vessel_id", "port_id"])):
        g = v.groupby(keys, sort=False)
        n_prev = g.cumcount()
        csum = g["log_stay"].cumsum() - v["log_stay"]
        out["vessel_prev_visits" + suffix] = n_prev
        out["vessel_prev_mean_log_stay" + suffix] = (csum / n_prev.replace(0, np.nan))
    # A ship cannot be alongside twice at once, but MMSI errors exist: drop history whose last
    # visit had not ended by this arrival.
    prev_dep = v.groupby("vessel_id")["departure_time"].shift()
    bad = prev_dep > v["arrival_time"]
    out.loc[bad, ["vessel_prev_visits", "vessel_prev_mean_log_stay"]] = np.nan
    out["visit_id"] = v["visit_id"]
    return out.reset_index(drop=True)


def time_features(t: pd.Series, arrival: pd.Series) -> pd.DataFrame:
    t = pd.to_datetime(t)
    return pd.DataFrame({
        "hour": t.dt.hour, "weekday": t.dt.weekday, "month": t.dt.month,
        "hurricane_season": t.dt.month.between(6, 11).astype(int),
        "arrival_hour": pd.to_datetime(arrival).dt.hour,
    }, index=t.index)


def build_checkpoints(visits: pd.DataFrame, port_calls: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cp in CHECKPOINTS_H:
        v = visits[visits["duration_hours"] > cp].copy()
        v["elapsed_h"] = float(cp)
        v["t"] = v["arrival_time"] + pd.to_timedelta(cp, unit="h")
        rows.append(v)
    df = pd.concat(rows, ignore_index=True)
    df["remaining_h"] = (df["departure_time"] - df["t"]).dt.total_seconds() / 3600
    df = pd.concat([df, time_features(df["t"], df["arrival_time"])], axis=1)
    df["vt_code"] = df["vesseltype"].map(VT_CODE)
    df = df.merge(vessel_history(visits), on="visit_id", how="left")
    df = pd.concat([df, context_features(df, visits, port_calls, np.ones(len(df), bool))], axis=1)
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
        return out[self.feature_names_]

    def get_feature_names_out(self, input_features=None):
        return np.array(self.feature_names_)
