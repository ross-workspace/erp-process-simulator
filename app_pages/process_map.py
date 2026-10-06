import streamlit as st

from dashboard import components as ui
from dashboard import panels, state

source = state.current_source()
analysis = source.analysis

with st.container(border=True, key="card-fullmap"):
    filters, controls = st.columns([1, 1], vertical_alignment="bottom")
    total_edges = max(len(analysis.transitions), 1)
    max_edges = filters.slider(
        "Paths shown", 1, total_edges, min(total_edges, 25),
        help="Keeps the most frequent arrows. Every activity stays on the map.",
    )
    with controls:
        panels.map_controls("fullmap")
    panels.process_map(analysis, max_edges=max_edges)

st.caption(
    "Each arrow means one event directly followed another in the same order. "
    "This is the process as recorded, not a BPMN model of how it should run."
)

activities, transitions = st.columns([1, 1.6])
with activities.container(border=True, key="card-activities", height="stretch"):
    st.subheader("Activities", anchor=False)
    frame = analysis.activities.assign(share=analysis.activities["cases"] / max(analysis.total_cases, 1))
    st.dataframe(
        frame,
        hide_index=True,
        column_config={
            "activity": "Activity",
            "cases": st.column_config.NumberColumn("Orders", format="localized"),
            "occurrences": st.column_config.NumberColumn("Events", format="localized"),
            "share": st.column_config.ProgressColumn("Share of orders", format="percent", min_value=0, max_value=1),
        },
    )

with transitions.container(border=True, key="card-transitions", height="stretch"):
    st.subheader("Transitions", anchor=False)
    frame = analysis.transitions.copy()
    frame["median"] = frame["median_hours"].map(ui.duration)
    frame["p90"] = frame["p90_hours"].map(ui.duration)
    st.dataframe(
        frame[["from_activity", "to_activity", "cases", "occurrences", "median", "p90"]],
        hide_index=True,
        column_config={
            "from_activity": "From",
            "to_activity": "To",
            "cases": st.column_config.NumberColumn("Orders", format="localized"),
            "occurrences": st.column_config.NumberColumn("Occurrences", format="localized"),
            "median": "Median wait",
            "p90": "P90 wait",
        },
    )
