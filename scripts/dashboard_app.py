"""Streamlit runtime dashboard built from config/dashboard.yaml + data/logs.jsonl.

Run with:
    streamlit run scripts/dashboard_app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_config() -> tuple[dict, dict]:
    dashboard = yaml.safe_load((REPO_ROOT / "config" / "dashboard.yaml").read_text(encoding="utf-8"))["dashboard"]
    slo = yaml.safe_load((REPO_ROOT / "config" / "slo.yaml").read_text(encoding="utf-8"))
    return dashboard, slo


def load_logs(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def window_df(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if df.empty:
        return df
    end = df["ts"].max()
    start = end - pd.Timedelta(minutes=minutes)
    return df[df["ts"] >= start]


def threshold_line(chart_df: pd.DataFrame, value: float, label: str) -> alt.Chart:
    return (
        alt.Chart(pd.DataFrame({"y": [value]}))
        .mark_rule(color="red", strokeDash=[4, 4])
        .encode(y="y", tooltip=alt.value(label))
    )


def render_latency(df: pd.DataFrame, panel: dict) -> None:
    sent = df[df["event"] == "response_sent"].copy()
    st.subheader(f"{panel['title']} ({panel['unit']})")
    if sent.empty:
        st.info("Không có dữ liệu response_sent trong time range.")
        return
    p50, p95, p99 = sent["latency_ms"].quantile([0.5, 0.95, 0.99])
    ttft_p95 = sent["ttft_ms"].quantile(0.95)
    cols = st.columns(4)
    cols[0].metric("P50 latency (ms)", f"{p50:.0f}")
    cols[1].metric("P95 latency (ms)", f"{p95:.0f}")
    cols[2].metric("P99 latency (ms)", f"{p99:.0f}")
    cols[3].metric("TTFT P95 (ms)", f"{ttft_p95:.0f}")

    threshold = panel["threshold"]
    st.caption(f"SLO threshold: {threshold['aggregation']} {threshold['operator']} {threshold['value']} {panel['unit']}")
    if threshold["operator"] == "lte" and p95 > threshold["value"]:
        st.error(f"Threshold breach: P95 latency {p95:.0f}ms > {threshold['value']}ms")

    per_minute = sent.set_index("ts").resample("1min")["latency_ms"].quantile(0.95).reset_index()
    line = alt.Chart(per_minute).mark_line(point=True).encode(x="ts:T", y="latency_ms:Q")
    rule = threshold_line(per_minute, threshold["value"], "SLO threshold")
    st.altair_chart(line + rule, width="stretch")


def render_traffic(df: pd.DataFrame, panel: dict) -> None:
    received = df[df["event"] == "request_received"].copy()
    st.subheader(f"{panel['title']} ({panel['unit']})")
    if received.empty:
        st.info("Không có dữ liệu request_received trong time range.")
        return
    per_minute = received.set_index("ts").resample("1min").size().reset_index(name="count")
    st.metric("Total requests", int(received.shape[0]))
    threshold = panel["threshold"]
    st.caption(f"SLO threshold: {threshold['aggregation']} {threshold['operator']} {threshold['value']} {panel['unit']}")
    st.bar_chart(per_minute.set_index("ts"))


def render_errors(df: pd.DataFrame, panel: dict) -> None:
    received = df[df["event"] == "request_received"]
    failed = df[df["event"] == "request_failed"]
    st.subheader(f"{panel['title']} ({panel['unit']})")
    error_rate_pct = (len(failed) / len(received) * 100) if len(received) else 0.0

    tool_events = df[df["tool_success"].notna()] if "tool_success" in df.columns else pd.DataFrame()
    retrieval_success_pct = (
        tool_events["tool_success"].mean() * 100 if not tool_events.empty else None
    )

    cols = st.columns(2)
    cols[0].metric("Error rate (%)", f"{error_rate_pct:.2f}")
    cols[1].metric(
        "Retrieval success (%)",
        f"{retrieval_success_pct:.2f}" if retrieval_success_pct is not None else "n/a",
    )

    threshold = panel["threshold"]
    st.caption(f"SLO threshold: {threshold['aggregation']} {threshold['operator']} {threshold['value']} {panel['unit']}")
    if threshold["operator"] == "lte" and error_rate_pct > threshold["value"]:
        st.error(f"Threshold breach: error rate {error_rate_pct:.2f}% > {threshold['value']}%")

    if "error_type" in failed.columns and not failed.empty:
        breakdown = failed["error_type"].value_counts().reset_index()
        breakdown.columns = ["error_type", "count"]
        st.bar_chart(breakdown.set_index("error_type"))
    else:
        st.info("Không có request_failed trong time range.")


def render_cost(df: pd.DataFrame, panel: dict) -> None:
    sent = df[df["event"] == "response_sent"].copy()
    st.subheader(f"{panel['title']} ({panel['unit']})")
    if sent.empty:
        st.info("Không có dữ liệu response_sent trong time range.")
        return
    total_cost = sent["cost_usd"].sum()
    st.metric("Total cost (USD)", f"{total_cost:.4f}")
    threshold = panel["threshold"]
    st.caption(f"SLO threshold: {threshold['aggregation']} {threshold['operator']} {threshold['value']} {panel['unit']}")
    if threshold["operator"] == "lte" and total_cost > threshold["value"]:
        st.error(f"Threshold breach: total cost ${total_cost:.4f} > ${threshold['value']}")
    per_minute = sent.set_index("ts").resample("1min")["cost_usd"].sum().reset_index()
    st.line_chart(per_minute.set_index("ts"))


def render_tokens(df: pd.DataFrame, panel: dict) -> None:
    sent = df[df["event"] == "response_sent"].copy()
    st.subheader(f"{panel['title']} ({panel['unit']})")
    if sent.empty:
        st.info("Không có dữ liệu response_sent trong time range.")
        return
    cols = st.columns(2)
    cols[0].metric("Total input tokens", int(sent["tokens_in"].sum()))
    cols[1].metric("Total output tokens", int(sent["tokens_out"].sum()))
    threshold = panel["threshold"]
    st.caption(f"SLO threshold: {threshold['aggregation']} {threshold['operator']} {threshold['value']} {panel['unit']}")
    per_minute = sent.set_index("ts").resample("1min")[["tokens_in", "tokens_out"]].sum()
    st.bar_chart(per_minute)


def render_quality(df: pd.DataFrame, panel: dict) -> None:
    sent = df[df["event"] == "response_sent"].copy()
    st.subheader(f"{panel['title']} ({panel['unit']})")
    if sent.empty:
        st.info("Không có dữ liệu response_sent trong time range.")
        return
    mean_quality = sent["quality_score"].mean()
    st.metric("Mean quality score", f"{mean_quality:.2f}")
    threshold = panel["threshold"]
    st.caption(f"SLO threshold: {threshold['aggregation']} {threshold['operator']} {threshold['value']} {panel['unit']}")
    if threshold["operator"] == "gte" and mean_quality < threshold["value"]:
        st.error(f"Threshold breach: mean quality {mean_quality:.2f} < {threshold['value']}")
    per_minute = sent.set_index("ts").resample("1min")["quality_score"].mean().reset_index()
    line = alt.Chart(per_minute).mark_line(point=True).encode(x="ts:T", y="quality_score:Q")
    rule = threshold_line(per_minute, threshold["value"], "Quality floor")
    st.altair_chart(line + rule, width="stretch")


PANEL_RENDERERS = {
    "latency": render_latency,
    "traffic": render_traffic,
    "errors": render_errors,
    "cost": render_cost,
    "tokens": render_tokens,
    "quality": render_quality,
}


def main() -> None:
    dashboard, slo = load_config()
    st.set_page_config(page_title=dashboard["title"], layout="wide")
    st.title(dashboard["title"])

    log_path = REPO_ROOT / "data" / "logs.jsonl"
    df = load_logs(log_path)
    time_range_minutes = dashboard["time_range_minutes"]
    df_window = window_df(df, time_range_minutes)

    st.sidebar.header("Config")
    st.sidebar.write(f"Source: `{log_path.relative_to(REPO_ROOT)}`")
    st.sidebar.write(f"Time range: last {time_range_minutes} minutes (ending at latest log event)")
    st.sidebar.write(f"Refresh: every {dashboard['refresh_seconds']}s (re-run script to refresh)")
    if not df.empty:
        st.sidebar.write(f"Window: {df_window['ts'].min()} → {df_window['ts'].max()}")
    st.sidebar.markdown("---")
    st.sidebar.subheader("SLO")
    st.sidebar.json(slo["primary_slo"])
    st.sidebar.subheader("Guardrails")
    st.sidebar.json(slo["guardrails"])

    if df.empty:
        st.warning(f"Chưa có log tại {log_path}. Chạy `python scripts/load_test.py` trước.")
        return

    for panel in dashboard["panels"]:
        PANEL_RENDERERS[panel["id"]](df_window, panel)
        st.divider()


if __name__ == "__main__":
    main()
