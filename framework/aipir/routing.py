"""Respond layer: route an alarm to the sub-process most likely affected.

At the moment an alarm is confirmed, the per-sensor contribution vector is ranked.
The alarm is routed to the process (P1 boiler, P2 turbine, P3 water treatment) of the
highest-ranked sensor among controllable processes. P4 points are the HIL simulator
(the virtual power plant model), which has no field equipment to recover, so they are
reported but not used as a routing target.
"""
from __future__ import annotations

import numpy as np

from .data import process_of

PLAYBOOKS = {
    "P1": "playbook-boiler: isolate DCS write path, restore last-known-good setpoints, verify FCV/LCV loops",
    "P2": "playbook-turbine: hold governor at safe speed reference, restore Mark VIe config, verify RPM loop",
    "P3": "playbook-water: switch PLC to local/manual, restore level setpoints, verify pump/valve states",
}


def route(contrib_row: np.ndarray, cols: list[str], top: int = 3):
    order = np.argsort(contrib_row)[::-1]
    ranked = [(cols[i], float(contrib_row[i])) for i in order[:top]]
    target = next((process_of(cols[i]) for i in order if process_of(cols[i]) in PLAYBOOKS), None)
    return target, ranked


def attacked_processes(labels_frame, s: int, e: int) -> set[str]:
    out = set()
    for p in ("P1", "P2", "P3"):
        col = f"attack_{p}"
        if col in labels_frame.columns and labels_frame[col].iloc[s:e + 1].any():
            out.add(p)
    return out
