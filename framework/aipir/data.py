"""Loading and preparing HAI telemetry.

HAI files are 1 Hz CSVs: a `time` column, process points named P<n>_<tag>, and
label columns (`attack`, `attack_P1`, `attack_P2`, `attack_P3`). HAI 20.07 uses
`;` as separator; HAI 21.03 uses `,`. Both are handled here.
"""
from __future__ import annotations

import gzip
import os

import numpy as np
import pandas as pd

LABEL_COLS = ["attack", "attack_P1", "attack_P2", "attack_P3"]
PROCESS_NAMES = {
    "P1": "Boiler process (Emerson Ovation DCS)",
    "P2": "Turbine process (GE Mark VIe DCS)",
    "P3": "Water-treatment process (Siemens S7-300 PLC)",
    "P4": "HIL simulation (steam-turbine + pumped-storage hydropower model)",
}


def _sep(path: str) -> str:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        head = f.readline()
    return ";" if head.count(";") > head.count(",") else ","


def load_file(path: str) -> pd.DataFrame:
    """Read one HAI CSV(.gz) with a parsed time index; float32 process values."""
    df = pd.read_csv(path, sep=_sep(path))
    df.columns = [c.strip() for c in df.columns]
    tcol = "time" if "time" in df.columns else df.columns[0]
    df[tcol] = pd.to_datetime(df[tcol])
    df = df.rename(columns={tcol: "time"}).set_index("time")
    for c in df.columns:
        if c not in LABEL_COLS:
            df[c] = df[c].astype("float32")
    for c in LABEL_COLS:
        if c in df.columns:
            df[c] = df[c].astype("int8")
    df.attrs["source_file"] = os.path.basename(path)
    return df


def sensor_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in LABEL_COLS]


def process_of(sensor: str) -> str:
    return sensor.split("_", 1)[0]


class Scaler:
    """Standardize with training mean/std; constant points are dropped, not divided by zero."""

    def __init__(self, min_std: float = 1e-6):
        self.min_std = min_std

    def fit(self, frames: list[pd.DataFrame], cols: list[str]) -> "Scaler":
        x = pd.concat([f[cols] for f in frames])
        self.mean_ = x.mean()
        self.std_ = x.std()
        self.cols_ = [c for c in cols if self.std_[c] > self.min_std]
        self.dropped_ = [c for c in cols if c not in self.cols_]
        self.min_ = x[self.cols_].min()
        self.max_ = x[self.cols_].max()
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        z = (df[self.cols_] - self.mean_[self.cols_]) / self.std_[self.cols_]
        return z.to_numpy(dtype=np.float32)
