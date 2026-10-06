"""ERP Process Analyzer: a local-first, evidence-led process-mining dashboard."""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    import erp_process_analyzer  # noqa: F401
except ModuleNotFoundError:  # running from a checkout without `pip install -e .`
    sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from dashboard import components as ui
from dashboard import state
from erp_process_analyzer.insights import resource_count

st.set_page_config(
    page_title="ERP Process Analyzer",
    page_icon=":material/account_tree:",
    layout="wide",
    initial_sidebar_state="expanded",
)
state.init_state()
ui.inject_css()
st.logo(str(ROOT / "dashboard" / "logo.svg"), size="large")

SUBTITLES = {
    "Overview": "Discover how your business really works. Find bottlenecks, analyze variants and simulate improvements.",
    "Process Map": "Every observed path between activities, built from the event log as a directly-follows graph.",
    "Bottlenecks": "Where orders spend their time waiting, and which teams receive the work.",
    "Process Variants": "The distinct end-to-end paths orders took, and what rework costs in cycle time.",
    "Cases": "Inspect any single order event by event, or filter and export the case list.",
    "Simulation": "Shorten one waiting step and see how completed orders would have moved.",
    "Upload CSV": "Bring your own Order-to-Cash event log. It is processed locally in this session.",
}

pages = {
    "": [
        st.Page("app_pages/overview.py", title="Overview", icon=":material/home:", default=True),
        st.Page("app_pages/process_map.py", title="Process Map", icon=":material/account_tree:"),
        st.Page("app_pages/bottlenecks.py", title="Bottlenecks", icon=":material/timer:"),
        st.Page("app_pages/variants.py", title="Process Variants", icon=":material/alt_route:"),
        st.Page("app_pages/cases.py", title="Cases", icon=":material/receipt_long:"),
        st.Page("app_pages/simulation.py", title="Simulation", icon=":material/science:"),
    ],
    "Data": [
        st.Page("app_pages/data_import.py", title="Upload CSV", icon=":material/upload:"),
    ],
}
page = st.navigation(pages)


def sidebar(source: state.Source) -> None:
    with st.sidebar:
        ui.html('<div class="side-label">Demo datasets</div>')
        st.session_state["_w_dataset_radio"] = source.label if source.is_demo else None
        st.radio(
            "Demo datasets",
            list(state.DEMOS),
            format_func=state.demo_label,
            key="_w_dataset_radio",
            on_change=state.select_dataset,
            args=("_w_dataset_radio",),
            label_visibility="collapsed",
        )
        events = source.analysis.raw_events
        people = resource_count(source.analysis)
        if people is not None and "resource" in events and events["resource"].eq("system").any():
            people -= 1
        departments = events["department"].replace("", None).nunique() if "department" in events else None
        stats = [
            ("Orders", f"{source.analysis.total_cases:,}"),
            ("Events", f"{len(events):,}"),
            ("Employees", f"{people:,}" if people is not None else "—"),
            ("Departments", f"{departments:,}" if departments else "—"),
        ]
        rows = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in stats)
        ui.html(
            f'<div class="company"><div class="company-name">{escape(source.company)}</div>'
            f'<div class="company-sum">{escape(source.summary)}</div><dl>{rows}</dl></div>'
        )


def header(source: state.Source) -> None:
    title_col, data_col, upload_col = st.columns([4.4, 1.7, 1.15], vertical_alignment="center")
    with title_col:
        st.title("ERP Process Analyzer" if page.title == "Overview" else page.title, anchor=False)
        ui.html(f'<div class="page-sub">{escape(SUBTITLES.get(page.title, ""))}</div>')
    with data_col:
        st.selectbox(
            "Dataset",
            state.dataset_options(),
            format_func=lambda name: f"{state.demo_label(name)} orders" if name in state.DEMOS else name,
            label_visibility="collapsed",
            **state.bind("dataset"),
        )
    with upload_col:
        with st.popover("Upload CSV", icon=":material/upload:", type="primary", width="stretch"):
            st.file_uploader(
                "Event log (CSV)", type="csv", key="upload_header",
                on_change=state.handle_upload, args=("upload_header",),
                help="Required columns: case_id, activity, timestamp",
            )
            st.caption("Required: `case_id`, `activity`, `timestamp`. Optional: `resource`, `department`, `order_value`.")
            st.page_link("app_pages/data_import.py", label="Format, timezone and sample file", icon=":material/info:")
    if st.session_state.upload_error:
        name, problems = st.session_state.upload_error
        st.error(f"**{name}** could not be imported:\n\n" + "\n".join(f"- {problem}" for problem in problems))


source = state.current_source()
sidebar(source)
header(source)
page.run()
