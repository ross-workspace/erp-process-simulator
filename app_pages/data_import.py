from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard import state

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_event_log.csv"

source = state.current_source()

upload, settings = st.columns([1.5, 1])
with upload.container(border=True, key="card-upload", height="stretch"):
    st.subheader("Upload an event log", anchor=False)
    st.file_uploader(
        "Event log (CSV, UTF-8, up to 30 MB)", type="csv", key="upload_page",
        on_change=state.handle_upload, args=("upload_page",),
    )
    if st.session_state.upload_error:
        name, problems = st.session_state.upload_error
        st.error(f"**{name}** could not be imported:\n\n" + "\n".join(f"- {problem}" for problem in problems))
    elif not source.is_demo:
        st.success(f"Analyzing **{source.company}**. Switch back to a demo from the sidebar at any time.")
    st.download_button(
        "Download a sample event log", SAMPLE.read_bytes(), file_name="sample_event_log.csv",
        mime="text/csv", icon=":material/download:", on_click="ignore",
    )

with settings.container(border=True, key="card-settings", height="stretch"):
    st.subheader("Settings", anchor=False)
    st.selectbox(
        "Timezone for timestamps without an offset", state.TIMEZONES, **state.bind("timezone"),
        help="Timestamps that carry an offset (e.g. +02:00 or Z) keep it. All results are shown in UTC.",
    )
    st.selectbox("Currency for order values", list(state.CURRENCIES), **state.bind("currency"))

with st.container(border=True, key="card-format"):
    st.subheader("Expected format", anchor=False)
    st.markdown("One row per recorded event. A *case* is one order; `Payment Received` marks it complete.")
    st.table(
        pd.DataFrame(
            [
                ("case_id", "Yes", "Order identifier shared by all its events", "ORD-000042"),
                ("activity", "Yes", "Event name", "Order Approved"),
                ("timestamp", "Yes", "ISO 8601, ideally with offset", "2026-01-05T09:42:00Z"),
                ("resource", "No", "Person or system that recorded it", "warehouse_03"),
                ("department", "No", "Team, used for workload views", "Warehouse"),
                ("order_value", "No", "Shown in case details", "24500"),
                ("event_order", "No", "Tie-breaker for equal timestamps", "3"),
            ],
            columns=["Column", "Required", "Meaning", "Example"],
        ).set_index("Column")
    )
    st.caption(
        "Typical sources: SAP tables VBAK/VBAP, LIKP, VBRK and BSAD (or their CDS views), Dynamics 365 "
        "sales order, shipment, invoice and payment journals. Export one event per status change and rename the columns."
    )

with st.container(border=True, key="card-quality"):
    st.subheader(f"Import quality · {source.label}", anchor=False)
    report = source.report
    with st.container(horizontal=True):
        st.metric("Rows", f"{report.rows:,}")
        st.metric("Orders", f"{report.cases:,}")
        st.metric("Exact duplicates", f"{report.duplicate_rows:,}")
        st.metric("Rows with tied timestamps", f"{report.tied_timestamp_rows:,}")
        st.metric("Events after payment", f"{source.analysis.post_payment_events:,}")
    for warning in report.warnings:
        st.warning(warning)
    if not report.warnings:
        st.success("No duplicates or ambiguous event order found.")
    export = source.events.drop(columns=["source_row", "sequence_ambiguous"], errors="ignore")
    st.download_button(
        "Export this dataset as CSV", export.to_csv(index=False).encode(),
        file_name=f"{source.label.lower().replace(' ', '_').replace('·', '').strip('_')}.csv",
        mime="text/csv", icon=":material/download:", on_click="ignore",
    )
