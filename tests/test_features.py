"""Leakage checks: every congestion feature must be reproducible from data visible at time t."""
import numpy as np
import pandas as pd
import pytest

from harborwise.config import PROCESSED

pytestmark = pytest.mark.skipif(not (PROCESSED / "checkpoints.parquet").exists(),
                                reason="run `python -m pipeline.run_all` first")


@pytest.fixture(scope="module")
def data():
    from harborwise.data import load_checkpoints, load_port_calls, load_visits
    return load_checkpoints(), load_visits(), load_port_calls()


def test_congestion_features_use_only_the_past(data):
    cp, visits, calls = data
    rows = cp.sample(60, random_state=0)
    for _, r in rows.iterrows():
        t = r["t"]
        # What an observer at time t can see: ships that have arrived; departures only if already happened.
        seen = visits[visits["arrival_time"] <= t]
        still_there = seen[~(seen["departure_time"] <= t)]
        port_now = still_there[still_there["port_id"] == r["port_id"]]
        assert r["port_occupancy"] == len(port_now) - 1  # minus the ship itself
        assert r["berth_occupancy_others"] == (port_now["berth_id"] == r["berth_id"]).sum() - 1
        left = seen[(seen["port_id"] == r["port_id"]) & (seen["departure_time"] > t - pd.Timedelta(hours=24))
                    & (seen["departure_time"] <= t)]
        assert r["port_departures_24h_comm"] == len(left)
        c = calls[(calls["port_id"] == r["port_id"]) & (calls["ts_start"] > t - pd.Timedelta(hours=24)) & (calls["ts_start"] <= t)]
        assert r["port_arrivals_24h_all"] == len(c)


def test_vessel_history_only_uses_finished_earlier_visits(data):
    cp, visits, _ = data
    rows = cp.dropna(subset=["vessel_prev_mean_log_stay"]).sample(40, random_state=1)
    for _, r in rows.iterrows():
        prev = visits[(visits["vessel_id"] == r["vessel_id"]) & (visits["arrival_time"] < r["arrival_time"])]
        assert (prev["departure_time"] <= r["arrival_time"]).all()
        assert r["vessel_prev_visits"] == len(prev)
        assert r["vessel_prev_mean_log_stay"] == pytest.approx(np.log1p(prev["duration_hours"]).mean())


def test_splits_are_chronological_and_purged(data):
    cp, _, _ = data
    tr, va, te = (cp[cp["split"] == s] for s in ("train", "val", "test"))
    assert tr["t"].max() < va["t"].min() and va["t"].max() < te["t"].min()
    assert tr["departure_time"].max() < va["t"].min()  # no training label reaches into validation
    assert va["departure_time"].max() < te["t"].min()


def test_feature_builder_handles_unseen_berths(data):
    from harborwise.features import FeatureBuilder
    cp, _, _ = data
    tr = cp[cp["split"] == "train"]
    fb = FeatureBuilder().fit(tr, tr["remaining_h"].to_numpy())
    x = cp[cp["split"] == "test"].head(5).copy()
    x["berth_id"], x["port_id"] = "never_seen", -1
    out = fb.transform(x)
    assert out[["med_total_berth_type", "med_total_berth", "med_total_port", "med_remaining_cp"]].notna().all().all()
    assert "vessel_id" not in out.columns and "berth_id" not in out.columns
