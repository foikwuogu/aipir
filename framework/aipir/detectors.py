"""Detectors compared in AIPIR.

Every detector is fit on standardized NORMAL telemetry only and returns, for a
standardized array Z (rows = seconds, cols = sensors):
    score   : 1-D anomaly score per second (higher = more anomalous), causal
    contrib : per-sensor contribution matrix (same shape as Z) used for routing,
              or None if the detector cannot attribute.
All smoothing is trailing (causal), so the score at second t uses data up to t only;
this keeps time-to-detect honest for real-time use.

Residual-based detectors (D1, D3) share one post-processing step, `RobustAggregate`:
each sensor's absolute residual is divided by its q-th percentile on normal training
data, clipped at `clip` (so one exogenous setpoint step cannot dominate), smoothed
over `smooth` seconds, and the score is the mean of the `topk` largest sensors.
"""
from __future__ import annotations

import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import Ridge


def causal_mean(a: np.ndarray, w: int) -> np.ndarray:
    """Trailing moving average over w rows (axis 0); first rows use the available history."""
    if w <= 1:
        return a.astype(np.float32)
    c = np.cumsum(np.nan_to_num(a, nan=0.0), axis=0, dtype=np.float64)
    out = c.copy()
    out[w:] = c[w:] - c[:-w]
    n = np.minimum(np.arange(1, len(a) + 1), w).astype(np.float64)
    if a.ndim == 2:
        n = n[:, None]
    return (out / n).astype(np.float32)


def lag_features(z: np.ndarray, lags: list[int]) -> np.ndarray:
    """Stack lagged copies of z; rows without full history are filled with the first row."""
    n, d = z.shape
    out = np.empty((n, d * len(lags)), dtype=np.float32)
    for i, L in enumerate(lags):
        sh = np.empty_like(z)
        sh[L:] = z[:-L]
        sh[:L] = z[0]
        out[:, i * d:(i + 1) * d] = sh
    return out


class RobustAggregate:
    def __init__(self, q=99.9, clip=5.0, smooth=10, topk=5):
        self.q, self.clip, self.smooth, self.topk = q, clip, smooth, topk

    def fit(self, abs_resid: np.ndarray):
        self.spread_ = np.maximum(np.percentile(abs_resid, self.q, axis=0), 1e-3).astype(np.float32)
        return self

    def __call__(self, abs_resid: np.ndarray):
        r = abs_resid / self.spread_
        if self.clip is not None:
            r = np.minimum(r, self.clip)
        r = causal_mean(r, self.smooth)
        k = min(self.topk, r.shape[1])
        return np.partition(r, -k, axis=1)[:, -k:].mean(1), r


class StaticLimits:
    """D0: classic alarm limits. Per-sensor [min, max] of normal training data.
    Score = largest exceedance outside the band, in units of each sensor's normal range.
    The alarm margin is set by threshold calibration like every other detector."""
    name = "D0 Static limits"

    def fit(self, zs: list[np.ndarray]):
        z = np.vstack(zs)
        self.lo_, self.hi_ = z.min(0), z.max(0)
        self.rng_ = np.maximum(self.hi_ - self.lo_, 1e-6)
        return self

    def score(self, z):
        exc = np.maximum(z - self.hi_, 0) + np.maximum(self.lo_ - z, 0)
        contrib = (exc / self.rng_).astype(np.float32)
        return contrib.max(1), contrib


class PCAResidual:
    """D1: PCA reconstruction residual keeping `var` of normal variance.
    mode="spe": classic squared prediction error, mean over sensors.
    mode="robust": the shared RobustAggregate post-processing."""
    name = "D1 PCA residual"

    def __init__(self, var=0.95, smooth=10, stride=3, mode="robust", q=99.9, clip=5.0, topk=5):
        self.var, self.smooth, self.stride, self.mode = var, smooth, stride, mode
        self.agg = RobustAggregate(q, clip, smooth, topk)

    def _abs_resid(self, z):
        return np.abs(z - self.pca_.inverse_transform(self.pca_.transform(z))).astype(np.float32)

    def fit(self, zs):
        z = np.vstack([a[::self.stride] for a in zs])
        self.pca_ = PCA(n_components=self.var, svd_solver="full").fit(z)
        r = self._abs_resid(z)
        self.scale_ = np.maximum((r ** 2).mean(0), 1e-6)
        self.agg.fit(r)
        return self

    def score(self, z):
        r = self._abs_resid(z)
        if self.mode == "spe":
            c = causal_mean((r ** 2 / self.scale_).astype(np.float32), self.smooth)
            return c.mean(1), c
        return self.agg(r)


class IForest:
    """D2: Isolation Forest outlier score (no per-sensor attribution)."""
    name = "D2 Isolation Forest"

    def __init__(self, n=100, sample=60000, smooth=10, seed=0):
        self.n, self.sample, self.smooth, self.seed = n, sample, smooth, seed

    def fit(self, zs):
        z = np.vstack(zs)
        rng = np.random.default_rng(self.seed)
        idx = rng.choice(len(z), size=min(self.sample, len(z)), replace=False)
        self.m_ = IsolationForest(n_estimators=self.n, random_state=self.seed, n_jobs=-1).fit(z[idx])
        return self

    def score(self, z):
        s = -self.m_.score_samples(z).astype(np.float32)
        return causal_mean(s, self.smooth), None


class AIPIRPredictive:
    """D3: the AIPIR predictive detector.

    Residual channels, learned from normal operation only:
      forecast    - ridge model predicting every sensor 1 s ahead from lagged history of all
                    sensors (temporal expectation: "what should the plant do next?")
      consistency - ridge model predicting every sensor from the *current* values of all
                    other sensors (physical-coupling expectation: "do the sensors agree?")
    With two channels the per-sensor residual is the larger of the two after normalization.
    The per-sensor residual matrix is returned so alerts can be routed to a sub-process.
    """
    name = "D3 AIPIR predictive"

    def __init__(self, lags=(1, 2, 3, 5, 10, 20, 30), alpha=1.0, stride=3,
                 channels=("forecast",), q=99.9, clip=5.0, smooth=10, topk=5):
        self.lags, self.alpha, self.stride = list(lags), alpha, stride
        self.channels = tuple(channels)
        self.cfg = dict(q=q, clip=clip, smooth=smooth, topk=topk)

    def _forecast_resid(self, z):
        return np.abs(z - self.f_.predict(lag_features(z, self.lags)).astype(np.float32))

    def _consistency_resid(self, z):
        return np.abs(z - (z @ self.cw_ + self.cb_)).astype(np.float32)

    def _resid(self, ch, z):
        return self._forecast_resid(z) if ch == "forecast" else self._consistency_resid(z)

    def fit(self, zs):
        d, L = zs[0].shape[1], max(self.lags)
        if "forecast" in self.channels:
            X = np.vstack([lag_features(a, self.lags)[L::self.stride] for a in zs])
            Y = np.vstack([a[L::self.stride] for a in zs])
            self.f_ = Ridge(alpha=self.alpha).fit(X, Y)
            del X, Y
        if "consistency" in self.channels:
            Z = np.vstack([a[::self.stride] for a in zs])
            self.cw_ = np.zeros((d, d), dtype=np.float32)
            self.cb_ = np.zeros(d, dtype=np.float32)
            for j in range(d):
                others = np.r_[0:j, j + 1:d]
                m = Ridge(alpha=self.alpha).fit(Z[:, others], Z[:, j])
                self.cw_[others, j] = m.coef_
                self.cb_[j] = m.intercept_
        self.aggs_ = {}
        for ch in self.channels:
            r = np.vstack([self._resid(ch, a)[L::self.stride] for a in zs])
            self.aggs_[ch] = RobustAggregate(**self.cfg).fit(r)
        return self

    def score(self, z):
        parts = [self.aggs_[ch](self._resid(ch, z))[1] for ch in self.channels]
        contrib = np.maximum.reduce(parts) if len(parts) > 1 else parts[0]
        k = min(self.cfg["topk"], contrib.shape[1])
        return np.partition(contrib, -k, axis=1)[:, -k:].mean(1), contrib
