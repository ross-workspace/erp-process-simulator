import streamlit as st

from dashboard import components as ui
from dashboard import panels, state

source = state.current_source()
analysis = source.analysis
cases = analysis.cases

with st.container(border=True, key="card-case-detail"):
    title, lookup = st.columns([1, 1.2], vertical_alignment="center")
    title.subheader("Order timeline", anchor=False)
    with lookup:
        chosen = panels.case_lookup(analysis, key="cases")
    if chosen:
        case = cases.loc[cases["case_id"].eq(chosen)].iloc[0]
        with st.container(horizontal=True):
            st.metric("Status", "Paid" if case["completed"] else "Open")
            st.metric("Events", f"{case['event_count']:,}")
            st.metric("Cycle time", ui.duration(case["cycle_hours"], long=True))
            st.metric("Loops back", "Yes" if case["rework"] else "No")
        st.dataframe(ui.case_events(analysis, chosen), hide_index=True)
        if case["sequence_ambiguous"]:
            st.warning("Some events in this order share a timestamp without an event_order, so CSV row order was used.")
        if case["post_payment_events"]:
            st.info(f"{case['post_payment_events']} event(s) after payment are shown but excluded from process metrics.")

with st.container(border=True, key="card-case-list"):
    st.subheader("Browse orders", anchor=False)
    view = st.segmented_control(
        "Show", ["All", "Paid", "Open", "With rework", "Slowest 5%"], default="All", key="case_filter",
        label_visibility="collapsed",
    )
    listing = cases
    if view == "Paid":
        listing = cases.loc[cases["completed"]]
    elif view == "Open":
        listing = cases.loc[~cases["completed"]]
    elif view == "With rework":
        listing = cases.loc[cases["rework"]]
    elif view == "Slowest 5%":
        threshold = cases["cycle_hours"].quantile(0.95)
        listing = cases.loc[cases["cycle_hours"].ge(threshold)].sort_values("cycle_hours", ascending=False)
    table = listing.assign(
        cycle_days=listing["cycle_hours"] / 24,
        path=listing["variant"].map(lambda steps: " → ".join(ui.short(step) for step in steps)),
        started=listing["first_event"].dt.strftime("%Y-%m-%d %H:%M"),
    )[["case_id", "started", "completed", "cycle_days", "event_count", "rework", "path"]]
    st.dataframe(
        table,
        hide_index=True,
        height=420,
        column_config={
            "case_id": "Order",
            "started": "Created (UTC)",
            "completed": st.column_config.CheckboxColumn("Paid"),
            "cycle_days": st.column_config.NumberColumn("Cycle (days)", format="%.1f"),
            "event_count": "Events",
            "rework": st.column_config.CheckboxColumn("Rework"),
            "path": st.column_config.TextColumn("Path", width="large"),
        },
    )
    st.download_button(
        f"Download {len(table):,} orders as CSV",
        table.to_csv(index=False).encode(),
        file_name=f"orders_{(view or 'all').lower().replace(' ', '_').replace('%', 'pct')}.csv",
        mime="text/csv",
        icon=":material/download:",
        on_click="ignore",
    )
