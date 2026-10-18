"""Loaders for the processed tables written by pipeline.build_dataset / build_features."""
from functools import lru_cache

import pandas as pd

from harborwise.config import PROCESSED, SEGMENTS, active_segment


def _need(name: str):
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing. Run `python -m pipeline.run_all` first.")
    return path


@lru_cache(maxsize=None)
def load_visits() -> pd.DataFrame:
    return pd.read_parquet(_need("visits.parquet"))


@lru_cache(maxsize=None)
def load_port_calls() -> pd.DataFrame:
    return pd.read_parquet(_need("port_calls.parquet"))


@lru_cache(maxsize=None)
def load_service_stops() -> pd.DataFrame:
    """Stops by non-commercial craft (tugs, pilots, barges, unknown type) inside berth polygons."""
    return pd.read_parquet(_need("service_stops.parquet"))


@lru_cache(maxsize=None)
def load_berths() -> pd.DataFrame:
    return pd.read_parquet(_need("berths.parquet"))


@lru_cache(maxsize=None)
def load_ports() -> pd.DataFrame:
    return pd.read_parquet(_need("ports.parquet"))


def load_checkpoints(segment: str | None = None) -> pd.DataFrame:
    """Checkpoint rows for one segment (default: the active one). Pass segment="all" for every type."""
    cp = pd.read_parquet(_need("checkpoints.parquet"))
    seg = segment or active_segment()
    return cp if seg == "all" else cp[cp["vesseltype"].isin(SEGMENTS[seg])].reset_index(drop=True)


def split_xy(cp: pd.DataFrame, split: str):
    part = cp[cp["split"] == split]
    return part, part["remaining_h"].to_numpy()
