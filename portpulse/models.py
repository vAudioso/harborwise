"""Model wrappers that bundle preprocessing + estimator so one joblib file is all the API needs."""
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from portpulse.config import CHECKPOINTS_H, QUANTILES
from portpulse.features import FeatureBuilder, _floor_checkpoint


def make_prep(feature_set: str = "full", scaler=None) -> Pipeline:
    steps = [("features", FeatureBuilder(feature_set=feature_set)),
             ("impute", SimpleImputer(strategy="median"))]
    if scaler is not None:
        steps.append(("scale", scaler))
    return Pipeline(steps).set_output(transform="pandas")


def _is_xgb(model) -> bool:
    return type(model).__module__.startswith("xgboost")


class RemainingTimeModel:
    """Point prediction of hours until the ship leaves the berth."""

    def __init__(self, prep: Pipeline, model, log_target: bool):
        self.prep, self.model, self.log_target = prep, model, log_target

    def fit(self, X, y, X_val=None, y_val=None):
        self.prep.fit(X, y)
        Z = self.prep.transform(X)
        yt = np.log1p(y) if self.log_target else y
        if _is_xgb(self.model) and X_val is not None:
            Zv = self.prep.transform(X_val)
            yv = np.log1p(y_val) if self.log_target else y_val
            self.model.fit(Z, yt, eval_set=[(Zv, yv)], verbose=False)
        else:
            self.model.fit(Z, yt)
        return self

    def predict(self, X) -> np.ndarray:
        p = self.model.predict(self.prep.transform(X))
        return np.clip(np.expm1(p) if self.log_target else p, 0, None)

    @property
    def feature_names(self):
        return list(self.prep[-1].get_feature_names_out())


class MedianBaseline:
    """Median remaining time from training data, with a fallback chain of grouping levels."""

    LEVELS = {"global": [], "port": [["port_id", "cp"], ["cp"]],
              "berth": [["berth_id", "cp"], ["port_id", "cp"], ["vesseltype", "cp"], ["cp"]]}

    def __init__(self, level: str, min_count: int = 10):
        self.level, self.min_count = level, min_count

    def fit(self, X: pd.DataFrame, y):
        d = X[["berth_id", "port_id", "vesseltype"]].copy()
        d["cp"], d["y"] = _floor_checkpoint(X["elapsed_h"].to_numpy()), y
        self.global_ = float(np.median(y))
        self.tables_ = []
        for keys in self.LEVELS[self.level]:
            g = d.groupby(keys)["y"].agg(["median", "size"])
            self.tables_.append((keys, g.loc[g["size"] >= self.min_count, "median"]))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        d = X[["berth_id", "port_id", "vesseltype"]].copy()
        d["cp"] = _floor_checkpoint(X["elapsed_h"].to_numpy())
        out = pd.Series(np.nan, index=d.index)
        for keys, tbl in self.tables_:
            idx = pd.MultiIndex.from_frame(d[keys]) if len(keys) > 1 else d[keys[0]]
            out = out.fillna(pd.Series(tbl.reindex(idx).to_numpy(), index=d.index))
        return out.fillna(self.global_).to_numpy()


class ClearanceQuantileModel:
    """P25/P50/P90 of hours until the berth clears.

    XGBoost multi-quantile regression on log1p(hours) (quantiles survive monotone transforms),
    then a split-conformal shift per quantile fitted on validation data so that the stated
    coverage holds on data the model did not train on.
    """

    def __init__(self, prep: Pipeline, model, quantiles=QUANTILES):
        self.prep, self.model, self.quantiles = prep, model, tuple(quantiles)
        self.shift_ = np.zeros(len(self.quantiles))

    def fit(self, X, y, X_val, y_val):
        self.prep.fit(X, y)
        Z, Zv = self.prep.transform(X), self.prep.transform(X_val)
        self.model.fit(Z, np.log1p(y), eval_set=[(Zv, np.log1p(y_val))], verbose=False)
        return self

    def _raw(self, X) -> np.ndarray:
        p = np.asarray(self.model.predict(self.prep.transform(X)))
        return p.reshape(len(X), -1)

    def calibrate(self, X_val, y_val):
        resid = np.log1p(y_val)[:, None] - self._raw(X_val)
        self.shift_ = np.array([np.quantile(resid[:, i], q) for i, q in enumerate(self.quantiles)])
        return self

    def predict(self, X) -> np.ndarray:
        q = np.sort(self._raw(X) + self.shift_, axis=1)  # enforce P25 <= P50 <= P90
        return np.clip(np.expm1(q), 0, None)


class ClearWithinClassifier:
    """P(berth clears within N hours): prep -> estimator -> isotonic calibration -> threshold."""

    def __init__(self, prep: Pipeline, model, onehot_vt: bool, sampler_name: str):
        self.prep, self.model, self.onehot_vt, self.sampler_name = prep, model, onehot_vt, sampler_name
        self.calibrator = None
        self.threshold = 0.5

    @staticmethod
    def expand_vt(Z: pd.DataFrame | np.ndarray, columns) -> np.ndarray:
        """Replace the vt_code column with one-hot columns (after any resampling)."""
        Z = pd.DataFrame(np.asarray(Z), columns=columns)
        codes = Z.pop("vt_code").round().astype(int).clip(0, 4)
        oh = np.eye(5)[codes.to_numpy()]
        return np.hstack([Z.to_numpy(), oh])

    def _matrix(self, Z):
        cols = list(self.prep[-1].get_feature_names_out()) if hasattr(self.prep[-1], "get_feature_names_out") else None
        return self.expand_vt(Z, cols) if self.onehot_vt else np.asarray(Z)

    def raw_proba(self, X) -> np.ndarray:
        return self.model.predict_proba(self._matrix(self.prep.transform(X)))[:, 1]

    def predict_proba(self, X) -> np.ndarray:
        p = self.raw_proba(X)
        return self.calibrator.predict(p) if self.calibrator is not None else p

    def predict(self, X) -> np.ndarray:
        return (self.predict_proba(X) >= self.threshold).astype(int)


__all__ = ["make_prep", "RemainingTimeModel", "MedianBaseline", "ClearanceQuantileModel", "ClearWithinClassifier",
           "CHECKPOINTS_H"]
