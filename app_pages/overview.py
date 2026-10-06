import streamlit as st

from dashboard import components as ui
from dashboard import panels, state
from erp_process_analyzer.insights import bottlenecks, period_change

source = state.current_source()
analysis = source.analysis
ranked = bottlenecks(analysis)

ui.kpi_cards(analysis, period_change(analysis))

map_col, insight_col = st.columns([3.15, 1.1])
with map_col.container(border=True, key="card-map", height="stretch"):
    title, controls = st.columns([1, 1.15], vertical_alignment="center")
    with title:
        st.subheader(
            "Process Map", anchor=False,
            help="A directly-follows graph: an arrow A → B means B was the very next event after A in the same order.",
        )
    with controls:
        panels.map_controls("overview", expand_to="app_pages/process_map.py")
    st.caption("Interactive view of the actual process flow discovered from your data. Hover any step or arrow for details.")
    panels.process_map(analysis, max_edges=14)

with insight_col.container(border=True, key="card-insights", height="stretch"):
    st.subheader("Process Insights", anchor=False, help="Headline facts computed from the current event log.")
    ui.insights(analysis, ranked)

main_col, sim_col = st.columns([2.2, 1])
with main_col:
    left, right = st.columns(2)
    with left.container(border=True, key="card-bottlenecks", height="stretch"):
        ui.panel_header(
            "Top Bottlenecks",
            "Transitions ranked by total waiting time. High = over 25% of all waiting time or a P90 at least 4× the median; "
            "Medium = over 5% or 2.5×. A long wait is a place to look, not proof of its cause.",
            "app_pages/bottlenecks.py",
        )
        ui.bottleneck_table(ranked)
    with right.container(border=True, key="card-variants", height="stretch"):
        ui.panel_header(
            "Process Variants",
            "A variant is one complete sequence of activities. Bars compare each variant with the most common one.",
            "app_pages/variants.py",
        )
        ui.variant_table(analysis)

    with st.container(border=True, key="card-case"):
        title, lookup = st.columns([1, 1.4], vertical_alignment="center")
        with title:
            st.subheader("Case Details", anchor=False, help="Every recorded event for one order, in process order.")
        with lookup:
            chosen = panels.case_lookup(analysis, key="overview")
        if chosen:
            ui.case_table(ui.case_events(analysis, chosen))

with sim_col.container(border=True, key="card-sim", height="stretch"):
    st.subheader(
        "What-if Simulation", anchor=False,
        help="Removes a share of the selected waiting time from each completed order and recomputes cycle time. "
        "It does not model capacity or queues.",
    )
    panels.simulation(analysis, ranked, key="overview")
