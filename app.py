"""ERP Process Analyzer: a local-first, evidence-led process-mining demo."""

from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from erp_process_analyzer import DataValidationError, analyze, load_events, simulate_transition
from erp_process_analyzer.analyzer import Analysis
from erp_process_analyzer.importer import ImportReport
from erp_process_analyzer.visuals import make_process_map

ROOT = Path(__file__).resolve().parent
DEMOS = {
    "Messy Process · 10,000 orders": ROOT / "data" / "demo_messy.csv",
    "Clean Process · 2,000 orders": ROOT / "data" / "demo_clean.csv",
    "Warehouse Delay · 3,000 orders": ROOT / "data" / "demo_warehouse.csv",
}

st.set_page_config(
    page_title="ERP Process Analyzer",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
  :root { --ink:#111c36; --muted:#60708e; --blue:#405cf5; --line:#e4eaf4; }
  .stApp { background:#f4f7fc; color:var(--ink); }
  .block-container { max-width:1600px; padding-top:1.65rem; }
  [data-testid="stSidebar"] { background:#101c31; }
  [data-testid="stSidebar"] { color:#e7edfc; }
  [data-testid="stSidebar"] label, [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#e7edfc; }
  [data-testid="stSidebar"] [role="combobox"] { color:#17233f !important; }
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background:#eef3fb; }
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * { color:#53617b !important; }
  h1,h2,h3 { color:#111b36; letter-spacing:-.035em; }
  h1 { font-weight:800; font-size:2rem; margin-bottom:0; }
  h2 { font-size:1.2rem; }
  h3 { font-size:1rem; }
  [data-testid="stVerticalBlockBorderWrapper"] { background:#fff !important; border:1px solid var(--line); border-radius:13px; box-shadow:0 1px 2px rgba(22,39,75,.03); }
  .eyebrow { color:#5369a8; font-size:.7rem; font-weight:800; text-transform:uppercase; letter-spacing:.12em; }
  .subline { color:var(--muted); margin-top:-.35rem; margin-bottom:1.1rem; }
  .metric-card { background:#fff; border:1px solid var(--line); border-radius:12px; min-height:112px; padding:16px 18px; box-shadow:0 1px 2px rgba(22,39,75,.03); }
  .metric-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:14px 0; }
  .metric-label { color:#61718e; font-size:.79rem; font-weight:600; }
  .metric-value { color:#0e1933; font-size:1.54rem; font-weight:800; margin:8px 0 2px; letter-spacing:-.035em; }
  .metric-note { color:#8996aa; font-size:.68rem; }
  .insight-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(165px,1fr)); gap:10px; margin:5px 0 12px; }
  .insight { background:#fff; border:1px solid var(--line); border-radius:12px; padding:15px 17px; min-height:100px; }
  .insight-k { font-size:.72rem; color:#71809a; }
  .insight-v { font-size:.99rem; font-weight:750; color:#192744; }
  .insight-note { font-size:.7rem; color:#71809a; }
  .side-brand { font-size:1.2rem; font-weight:800; color:white; line-height:1.15; margin:10px 0 25px; }
  .side-brand small { display:inline-block; background:#405cf5; padding:3px 7px; border-radius:6px; font-size:.62rem; vertical-align:middle; }
  .side-caption { font-size:.72rem; color:#abb8d1; margin:8px 0; }
  .small-note { color:#72819b; font-size:.78rem; }
  div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] { background:#405cf5; border-color:#405cf5; }
  [data-testid="stDataFrame"] { border:1px solid #e6ebf4; border-radius:9px; }
</style>
""",
    unsafe_allow_html=True,
)


def duration(hours: float | None) -> str:
    if hours is None or pd.isna(hours):
        return "—"
    if hours < 1:
        return f"{hours * 60:.0f} min"
    if hours < 24:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} days"


def metric_card(label: str, value: str, note: str) -> str:
    return (
        f'<div class="metric-card"><div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(value)}</div>'
        f'<div class="metric-note">{escape(note)}</div></div>'
    )


def insight(label: str, value: str, note: str) -> str:
    return (
        f'<div class="insight"><div class="insight-k">{escape(label)}</div>'
        f'<div class="insight-v">{escape(value)}</div>'
        f'<div class="insight-note">{escape(note)}</div></div>'
    )


@st.cache_data(show_spinner=False)
def load_demo(path: str) -> tuple[pd.DataFrame, ImportReport]:
    return load_events(path)


@st.cache_data(show_spinner=False)
def load_upload(payload: bytes, timezone: str) -> tuple[pd.DataFrame, ImportReport]:
    return load_events(BytesIO(payload), timezone_for_naive=timezone)


@st.cache_data(show_spinner=False)
def analyze_cached(events: pd.DataFrame) -> Analysis:
    return analyze(events)


def sidebar() -> tuple[str, pd.DataFrame, ImportReport, str]:
    with st.sidebar:
        st.markdown('<div class="side-brand">⬡ &nbsp; ERP Process<br>&nbsp;&nbsp;&nbsp;&nbsp; Analyzer <small>MVP</small></div>', unsafe_allow_html=True)
        page = st.radio(
            "Navigate",
            ["Overview", "Process Map", "Transitions", "Process Variants", "Cases", "Simulation"],
            label_visibility="collapsed",
        )
        st.divider()
        st.markdown('<div class="eyebrow">Data source</div>', unsafe_allow_html=True)
        demo_name = st.selectbox("Demo dataset", list(DEMOS), label_visibility="collapsed")
        upload = st.file_uploader("Or upload a CSV", type="csv", help="Required: case_id, activity, timestamp")
        timezone = st.selectbox("Timezone for timestamps without an offset", ["UTC", "Europe/Prague", "America/New_York"], help="Timestamps with an offset keep their own timezone before UTC conversion.")
        st.markdown('<div class="side-caption">Synthetic demo data · one order per case</div>', unsafe_allow_html=True)

        try:
            if upload is not None:
                if upload.size > 30 * 1024 * 1024:
                    raise DataValidationError(["CSV exceeds the 30 MB MVP upload limit."])
                events, report = load_upload(upload.getvalue(), timezone)
                source_name = f"Uploaded: {upload.name}"
            else:
                selected = DEMOS[demo_name]
                events, report = load_demo(str(selected))
                source_name = demo_name
        except (DataValidationError, FileNotFoundError) as exc:
            st.error(str(exc))
            st.stop()

        st.divider()
        st.markdown(f"**{report.cases:,}** orders · **{report.rows:,}** events")
        with st.expander("Import quality"):
            st.write(f"Timezone for naive timestamps: {report.timezone_for_naive}")
            if report.warnings:
                for warning in report.warnings:
                    st.warning(warning)
            else:
                st.success("No duplicates or timestamp ties found.")
    return page, events, report, source_name


def top_header(source_name: str) -> None:
    st.title("ERP Process Analyzer")
    st.markdown(
        f'<div class="subline">Discover how orders moved, inspect elapsed time, and explore a timing scenario. &nbsp;·&nbsp; <b>{escape(source_name)}</b></div>',
        unsafe_allow_html=True,
    )


def kpi_row(result: Analysis, report: ImportReport) -> None:
    resources = (
        int(result.raw_events["resource"].replace("", pd.NA).nunique())
        if "resource" in result.raw_events else None
    )
    values = [
        ("Cases", f"{result.total_cases:,}", f"{result.completed_cases:,} complete · {result.open_cases:,} open"),
        ("Events", f"{report.rows:,}", "Recorded rows"),
        ("Activities", f"{len(result.activities):,}", "Observed process steps"),
        ("Resources", f"{resources:,}" if resources is not None else "—", "People / systems in log"),
        ("Average cycle", duration(result.mean_cycle_hours), "Complete orders · calendar time"),
        ("Variants", f"{len(result.variants):,}", "Distinct event sequences"),
    ]
    cards = "".join(metric_card(label, value, note) for label, value, note in values)
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)


def transition_table(result: Analysis, limit: int | None = None) -> None:
    frame = result.transitions.head(limit).copy() if limit else result.transitions.copy()
    if frame.empty:
        st.info("At least two events in a case are needed for transitions.")
        return
    frame["Transition"] = frame["from_activity"] + " → " + frame["to_activity"]
    frame["Median gap"] = frame["median_hours"].map(duration)
    frame["P90 gap"] = frame["p90_hours"].map(duration)
    frame["Case-hours"] = frame["total_case_hours"].round(1)
    st.dataframe(
        frame[["Transition", "Median gap", "P90 gap", "cases", "occurrences", "Case-hours"]].rename(
            columns={"cases": "Cases", "occurrences": "Occurrences"}
        ),
        hide_index=True,
        width="stretch",
    )


def variant_table(result: Analysis, limit: int | None = None) -> None:
    frame = result.variants.head(limit).copy() if limit else result.variants.copy()
    if frame.empty:
        st.info("No process variants in this log.")
        return
    frame["Flow"] = frame["variant"].map(lambda sequence: " → ".join(sequence))
    frame["Share"] = frame["share"].map(lambda value: f"{value:.1%}")
    frame["Rework"] = frame["rework"].map(lambda value: "Yes" if value else "No")
    st.dataframe(frame[["Flow", "cases", "Share", "Rework"]].rename(columns={"cases": "Cases"}), hide_index=True, width="stretch")


def scenario_panel(result: Analysis, *, compact: bool = False) -> None:
    st.subheader("What-if scenario" if compact else "Historical timing scenario")
    st.caption("Reduce one recorded transition gap; the model shifts later events by the same amount.")
    if result.transitions.empty or result.completed_cases == 0:
        st.info("This scenario needs a transition and at least one completed case.")
        return
    options = [
        (row.from_activity, row.to_activity)
        for row in result.transitions.itertuples(index=False)
    ]
    preferred = ("Order Approved", "Picking Started")
    default_index = options.index(preferred) if preferred in options else 0
    selected = st.selectbox("Transition to change", options, index=default_index, format_func=lambda pair: f"{pair[0]} → {pair[1]}", key=f"transition_{compact}")
    percent = st.slider("Reduce elapsed gap by", min_value=0, max_value=100, value=50, step=5, format="%d%%", key=f"reduction_{compact}")
    scenario = simulate_transition(result, selected[0], selected[1], percent)
    edge = result.transitions.loc[
        result.transitions["from_activity"].eq(selected[0])
        & result.transitions["to_activity"].eq(selected[1])
    ].iloc[0]
    st.markdown(f"<div class='small-note'>Current median gap: <b>{duration(edge['median_hours'])}</b></div>", unsafe_allow_html=True)
    if compact:
        st.metric("Adjusted average cycle", duration(scenario.adjusted_mean_hours), f"{duration((scenario.current_mean_hours or 0) - (scenario.adjusted_mean_hours or 0))} less")
        st.caption(f"{scenario.affected_cases:,} completed cases affected · {scenario.removed_case_hours:,.0f} case-hours removed")
    else:
        left, middle, right = st.columns(3)
        left.metric("Current average cycle", duration(scenario.current_mean_hours))
        middle.metric("Adjusted average cycle", duration(scenario.adjusted_mean_hours))
        right.metric("Removed case-hours", f"{scenario.removed_case_hours:,.1f}")
        st.write(f"**{scenario.affected_cases:,} of {scenario.completed_cases:,} completed cases** contain this transition ({scenario.affected_occurrences:,} occurrences).")
        comparison = pd.DataFrame(
            {
                "Metric": ["Mean completed cycle", "Median completed cycle", "Affected cases", "Total elapsed case-hours removed"],
                "Current": [duration(scenario.current_mean_hours), duration(scenario.current_median_hours), f"{scenario.affected_cases:,}", "—"],
                "Adjusted": [duration(scenario.adjusted_mean_hours), duration(scenario.adjusted_median_hours), f"{scenario.affected_cases:,}", f"{scenario.removed_case_hours:,.1f} h"],
            }
        )
        st.dataframe(comparison, hide_index=True, width="stretch")
    st.caption("Assumption: each selected gap shrinks by the chosen percentage. No staffing, queues, parallel work, payment terms, or behaviour changes are modelled. Case-hours are elapsed order time, not employee hours or money saved.")


def case_panel(result: Analysis, *, compact: bool = False) -> None:
    st.subheader("Case details")
    default = result.cases.iloc[0]["case_id"] if len(result.cases) else ""
    requested = st.text_input("Search order ID", value=default, key=f"case_search_{compact}")
    match = result.cases.loc[result.cases["case_id"].eq(requested)]
    if match.empty:
        st.info("Enter an exact case ID from this dataset.")
        return
    case = match.iloc[0]
    status = "Complete" if case["completed"] else "Open"
    st.caption(f"{status} · {case['event_count']} recorded events · cycle {duration(case['cycle_hours'])} · rework {'yes' if case['rework'] else 'no'}")
    frame = result.raw_events.loc[result.raw_events["case_id"].eq(requested)].copy()
    frame["Next event gap"] = ((frame["timestamp"].shift(-1) - frame["timestamp"]).dt.total_seconds() / 3600).map(duration)
    frame["Timestamp (UTC)"] = frame["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    columns = ["Timestamp (UTC)", "activity", "Next event gap"]
    for optional in ("resource", "department", "order_value", "cost"):
        if optional in frame:
            columns.append(optional)
    st.dataframe(frame[columns].rename(columns={"activity": "Activity"}), hide_index=True, width="stretch")
    if case["sequence_ambiguous"]:
        st.warning("This case has tied event timestamps without an unambiguous event order.")
    if case["post_payment_events"]:
        st.warning(f"{case['post_payment_events']} event(s) after payment are shown here but excluded from process calculations.")


def main() -> None:
    page, events, report, source_name = sidebar()
    with st.spinner("Analyzing event log…"):
        result = analyze_cached(events)
    top_header(source_name)

    if page == "Overview":
        kpi_row(result, report)
        with st.container(border=True):
            st.subheader("Process map")
            st.caption("Observed directly-follows paths · arrow thickness reflects case frequency")
            st.plotly_chart(make_process_map(result, max_edges=18), width="stretch", config={"displayModeBar": False})
        st.subheader("Process insights")
        common = result.variants.iloc[0] if len(result.variants) else None
        insights = [
            insight("Most common variant", f"{common['share']:.1%}" if common is not None else "—", "Share of all cases"),
            insight("Approval rework", f"{result.rework_cases / result.total_cases:.1%}", f"{result.rework_cases:,} of {result.total_cases:,} cases"),
        ]
        if len(result.transitions):
            top = result.transitions.iloc[0]
            insights.append(insight("Largest elapsed-time burden", f"{top['from_activity']} → {top['to_activity']}", f"{top['total_case_hours']:,.0f} case-hours across the log"))
        insights.append(insight("Open cases", f"{result.open_cases:,}", "Excluded from completed cycle time"))
        st.markdown(f'<div class="insight-grid">{"".join(insights)}</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("Transitions to investigate")
            st.caption("Ranked by total elapsed case-hours; this does not establish the cause of a delay.")
            transition_table(result, limit=5)
        with st.container(border=True):
            st.subheader("Process variants")
            variant_table(result, limit=5)
        with st.container(border=True):
            scenario_panel(result, compact=True)
        with st.container(border=True):
            case_panel(result, compact=True)

    elif page == "Process Map":
        st.subheader("Observed process map")
        st.caption("Each edge means one event directly followed another in the same order. The map is not a BPMN model.")
        max_edges = st.slider("Maximum edges shown", 5, 60, 25)
        with st.container(border=True):
            st.plotly_chart(make_process_map(result, max_edges=max_edges), width="stretch")
        transition_table(result)

    elif page == "Transitions":
        st.subheader("Elapsed time between events")
        st.caption("Median and P90 are calendar time between adjacent recorded events. Total case-hours ranks investigation candidates, including payment terms and other external waits.")
        transition_table(result)
        st.info("A long elapsed gap does not prove a staff or warehouse bottleneck. Inspect the cases and business rules behind it.")

    elif page == "Process Variants":
        st.subheader("Process variants and rework")
        st.caption("One variant is the complete ordered event sequence for one order. Approval rework is Approved → Edited → Approved, including intervening events.")
        first, second, third = st.columns(3)
        first.metric("Unique variants", f"{len(result.variants):,}")
        second.metric("Approval rework", f"{result.rework_cases:,} of {result.total_cases:,}")
        third.metric("Rework rate", f"{result.rework_cases / result.total_cases:.1%}")
        variant_table(result)
        completed = result.cases.loc[result.cases["completed"]]
        if not completed.empty:
            comparison = completed.groupby("rework")["cycle_hours"].agg(["size", "median"]).reset_index()
            comparison["Cohort"] = comparison["rework"].map({True: "With approval rework", False: "Without approval rework"})
            comparison["Median cycle"] = comparison["median"].map(duration)
            st.subheader("Completed-case comparison")
            st.dataframe(comparison[["Cohort", "size", "Median cycle"]].rename(columns={"size": "Cases"}), hide_index=True)
            st.caption("This is an observed association. Other differences between these orders may explain the timing gap.")

    elif page == "Cases":
        case_panel(result)
        with st.expander("Browse cases"):
            listing = result.cases.head(100).copy()
            listing["Cycle"] = listing["cycle_hours"].map(duration)
            st.dataframe(listing[["case_id", "completed", "Cycle", "rework", "event_count"]], hide_index=True, width="stretch")
            st.caption("Showing first 100 cases. Search above for any exact case ID.")

    elif page == "Simulation":
        scenario_panel(result)

    with st.expander("Data and method notes"):
        st.write(f"Source: {source_name}. {report.rows:,} rows, {report.cases:,} cases. {result.post_payment_events:,} post-payment events excluded from process calculations.")
        st.write("Completed cycle time is first recorded event to first Payment Received. Open cases remain in the map and variants, but are excluded from cycle-time and scenario aggregates. All displayed gaps use calendar time.")
        if report.warnings:
            for warning in report.warnings:
                st.warning(warning)


if __name__ == "__main__":
    main()
