"""Online (one-second-at-a-time) scoring for the AIPIR predictive detector.

The batch detector and this streaming scorer must give the same score for the same
second; 02_build/03_qa checks that equivalence. The scorer keeps only the last
max(lag) + smooth rows in memory, so its cost per second is constant.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from .detectors import AIPIRPredictive
from .metrics import episodes
from .routing import route


class StreamingScorer:
    def __init__(self, bundle: dict):
        self.sc = bundle["scaler"]
        self.det: AIPIRPredictive = bundle["detector"]
        self.thr = float(bundle["threshold"])
        self.alarm = bundle["alarm"]
        self.cols = bundle["columns"]
        self.lags = self.det.lags
        self.L = max(self.lags)
        self.agg = self.det.aggs_["forecast"]
        self.hist = deque(maxlen=self.L + 1)        # standardized rows
        self.resid = deque(maxlen=self.agg.smooth)  # normalized, clipped residual rows
        self.first = None
        self.ep_start = None    # second at which the current alarm episode began
        self.gap = 10 ** 9      # seconds since last above-threshold second
        self.active = False
        self.t = 0

    def _features(self):
        rows = list(self.hist)
        cur = len(rows) - 1
        feats = []
        for L in self.lags:
            j = cur - L
            feats.append(rows[j] if j >= 0 else self.first)
        return np.concatenate(feats)[None, :]

    def update(self, raw_row: dict):
        """Feed one second of telemetry (dict sensor -> value). Returns a status dict."""
        z = np.array([(raw_row[c] - self.sc.mean_[c]) / self.sc.std_[c] for c in self.cols], dtype=np.float32)
        if self.first is None:
            self.first = z
        self.hist.append(z)
        pred = self.det.f_.predict(self._features())[0]
        r = np.abs(z - pred) / self.agg.spread_
        if self.agg.clip is not None:
            r = np.minimum(r, self.agg.clip)
        self.resid.append(r.astype(np.float32))
        contrib = np.mean(self.resid, axis=0)
        k = min(self.agg.topk, len(contrib))
        score = float(np.sort(contrib)[-k:].mean())
        # online episode logic equivalent to metrics.episodes (merge gap + debounce)
        if score > self.thr:
            if self.ep_start is None:
                self.ep_start = self.t
            self.gap = 0
            if self.t - self.ep_start + 1 >= self.alarm["min_dur"]:
                self.active = True
        else:
            self.gap += 1
            if self.gap > self.alarm["merge_gap"]:
                self.ep_start = None
                self.active = False
        target, ranked = route(contrib, self.cols) if self.active else (None, [])
        self.t += 1
        return {"t": self.t, "score": score, "threshold": self.thr, "alarm": self.active,
                "routed": target, "top_sensors": ranked, "contrib": contrib}


__all__ = ["StreamingScorer", "episodes"]
