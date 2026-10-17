"""Loaders for the processed tables written by pipeline.build_dataset / build_features."""
from functools import lru_cache

import pandas as pd

from harborwise.config import PROCESSED


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
def load_berths() -> pd.DataFrame:
    return pd.read_parquet(_need("berths.parquet"))


@lru_cache(maxsize=None)
def load_ports() -> pd.DataFrame:
    return pd.read_parquet(_need("ports.parquet"))


def load_checkpoints() -> pd.DataFrame:
    return pd.read_parquet(_need("checkpoints.parquet"))


def split_xy(cp: pd.DataFrame, split: str):
    part = cp[cp["split"] == split]
    return part, part["remaining_h"].to_numpy()
