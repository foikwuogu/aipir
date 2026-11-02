"""Lightweight live dashboard for the AIPIR detector service.

Mirrors the three panels of deploy/grafana/provisioning/dashboards/aipir.json
(anomaly score vs threshold, active alarm by process, top contributing
sensors) without needing Prometheus/Grafana/Docker: it polls the service's
own /metrics endpoint (started with `python -m aipir.service ...`) and
renders the same information with Streamlit.

The service is Zero-Trust (see framework/aipir/zerotrust.py): every call to
/metrics needs a bearer token with the `metrics:read` permission. In lab mode,
`source docs/training/lab_env.sh` mints one (`$VIEWER`); paste it into the
sidebar below or export it as AIPIR_VIEWER_TOKEN before launching Streamlit.

Run:  streamlit run dashboard/app.py
"""
from __future__ import annotations

import os
import re

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="AIPIR live dashboard", page_icon=":material/monitor_heart:", layout="wide")

GAUGE_RE = re.compile(r'^(?P<name>\w+)(\{(?P<labels>[^}]*)\})?\s+(?P<value>[-\d.eE+]+)\s*$')
MAX_POINTS = 300  # ~5 min of history at 1 point/s


def parse_labels(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    out = {}
    for pair in raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


@st.cache_data(ttl=1)
def fetch_metrics(url: str, token: str) -> tuple[dict, list[dict], list[dict]]:
    """Scrape the AIPIR /metrics endpoint. Cached for 1s so reruns within the
    same second reuse the same scrape instead of hammering the service."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(url, headers=headers, timeout=3)
    resp.raise_for_status()
    scalars: dict[str, float] = {}
    alarms: list[dict] = []
    residuals: list[dict] = []
    for line in resp.text.splitlines():
        if not line or line.startswith("#"):
            continue
        m = GAUGE_RE.match(line.strip())
        if not m:
            continue
        name, labels, value = m["name"], parse_labels(m["labels"]), float(m["value"])
        if name == "aipir_alarm":
            alarms.append({"process": labels.get("process", "?"), "alarm": value})
        elif name == "aipir_sensor_residual":
            residuals.append({"sensor": labels.get("sensor", "?"), "process": labels.get("process", "?"),
                               "residual": value})
        elif not labels:
            scalars[name] = value
    return scalars, alarms, residuals


if "history" not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=["t", "score", "threshold"])

with st.sidebar:
    st.header("Connection")
    url = st.text_input("Metrics URL", "http://localhost:9108/metrics")
    token = st.text_input("Bearer token (role aipir.viewer)", os.environ.get("AIPIR_VIEWER_TOKEN", ""),
                           type="password", help="source docs/training/lab_env.sh then paste $VIEWER")
    st.caption("Started via `python -m aipir.service --model ... --replay ... --port 9108`")
    refresh_s = st.slider("Refresh interval (s)", 0.5, 5.0, 1.0, 0.5)


@st.fragment(run_every=refresh_s)
def live_view():
    try:
        scalars, alarms, residuals = fetch_metrics(url, token)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not reach {url}: {exc}")
        return

    rows = scalars.get("aipir_rows_processed_total", 0)
    score = scalars.get("aipir_anomaly_score")
    threshold = scalars.get("aipir_threshold")

    top = st.columns(4)
    top[0].metric("Rows scored", f"{int(rows):,}")
    top[1].metric("Anomaly score", f"{score:.4f}" if score is not None else "-")
    top[2].metric("Threshold", f"{threshold:.4f}" if threshold is not None else "-")
    active = next((a["process"] for a in alarms if a["alarm"]), None)
    top[3].metric("Alarm routed to", active or "none")

    st.divider()
    left, right = st.columns([2, 1])

    with left:
        st.subheader("Anomaly score vs threshold")
        if score is not None and threshold is not None:
            hist = st.session_state.history
            hist.loc[len(hist)] = {"t": rows, "score": score, "threshold": threshold}
            if len(hist) > MAX_POINTS:
                st.session_state.history = hist.iloc[-MAX_POINTS:].reset_index(drop=True)
            st.line_chart(st.session_state.history, x="t", y=["score", "threshold"], width="stretch",
                           color=["#1f77b4", "#d62728"])
        else:
            st.info("Waiting for the first scored second...")

    with right:
        st.subheader("Active alarm by process")
        if alarms:
            for a in sorted(alarms, key=lambda r: r["process"]):
                icon = ":material/warning:" if a["alarm"] else ":material/check_circle:"
                state = "ALARM" if a["alarm"] else "normal"
                container = st.container(border=True, horizontal=True)
                container.markdown(f"{icon} **{a['process']}**")
                container.markdown(f"`{state}`")
        else:
            st.info("No alarm gauges yet.")

    st.divider()
    st.subheader("Top contributing sensors")
    if residuals:
        df = pd.DataFrame(residuals).sort_values("residual", ascending=False).head(10)
        st.bar_chart(df, x="sensor", y="residual", width="stretch")
    else:
        st.info("No sensor residuals yet.")


st.title(":material/monitor_heart: AIPIR live dashboard")
st.caption("Observe -> Predict -> Respond -> Recover, scraped live from the running detector service.")
live_view()
