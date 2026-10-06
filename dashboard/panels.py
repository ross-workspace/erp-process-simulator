"""Interactive panels shared by the overview and the detail pages."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from erp_process_analyzer import Analysis, Scenario, simulate_transition
from erp_process_analyzer.insights import summarize_scenario
from erp_process_analyzer.visuals import process_map_svg

from . import components as ui
from .state import bind

ZOOM_STEPS = [50, 75, 100, 125, 150, 200]
PREFERRED_SCENARIO = ("Order Approved", "Picking Started")


def _zoom(step: int) -> None:
    position = ZOOM_STEPS.index(st.session_state.map_zoom) if st.session_state.map_zoom in ZOOM_STEPS else 2
    st.session_state.map_zoom = ZOOM_STEPS[max(0, min(len(ZOOM_STEPS) - 1, position + step))]


def map_controls(key: str, *, expand_to: str | None = None) -> None:
    with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", gap="small"):
        st.selectbox(
            "Map metric", ["Frequency", "Duration"], label_visibility="collapsed", width=130, **bind("map_mode"),
            help="Frequency labels edges with case counts; Duration with the median time between the two events.",
        )
        st.button("", icon=":material/remove:", key=f"{key}_out", on_click=_zoom, args=(-1,), help="Zoom out")
        ui.html(f"<div class='zoom-label'>{st.session_state.map_zoom}%</div>")
        st.button("", icon=":material/add:", key=f"{key}_in", on_click=_zoom, args=(1,), help="Zoom in")
        if expand_to is not None:
            st.page_link(expand_to, label="", icon=":material/open_in_full:", help="Open the full process map")


def process_map(analysis: Analysis, *, max_edges: int = 18) -> None:
    svg = process_map_svg(analysis, mode=st.session_state.map_mode.lower(), max_edges=max_edges)
    zoom = st.session_state.map_zoom
    ui.html(f'<div class="pmap-wrap"><div style="width:{zoom}%;min-width:{zoom * 6}px">{svg}</div></div>')
    ui.legend()


def transition_options(analysis: Analysis) -> list[tuple[str, str]]:
    return list(zip(analysis.transitions["from_activity"], analysis.transitions["to_activity"]))


def default_transition(options: list[tuple[str, str]], ranked: pd.DataFrame) -> int:
    if PREFERRED_SCENARIO in options:
        return options.index(PREFERRED_SCENARIO)
    # Otherwise the slowest step that is not just waiting for the customer to pay.
    internal = ranked.loc[ranked["to_activity"].ne("Payment Received")]
    if len(internal):
        pair = (internal.iloc[0]["from_activity"], internal.iloc[0]["to_activity"])
        if pair in options:
            return options.index(pair)
    return 0


def simulation(analysis: Analysis, ranked: pd.DataFrame, *, key: str) -> Scenario | None:
    options = transition_options(analysis)
    if not options or analysis.completed_cases == 0:
        st.info("The simulation needs at least one transition and one completed order.")
        return None
    selected = st.selectbox(
        "Select transition to improve", options, index=default_transition(options, ranked),
        format_func=lambda pair: f"{pair[0]} → {pair[1]}", key=f"{key}_transition",
    )
    edge = analysis.transitions.loc[
        analysis.transitions["from_activity"].eq(selected[0]) & analysis.transitions["to_activity"].eq(selected[1])
    ].iloc[0]
    ui.html(
        f'<div class="current-wait"><span>Current median waiting time</span>'
        f"<b>{ui.duration(edge['median_hours'], long=True)}</b></div>"
    )
    with st.form(f"{key}_form", border=False):
        percent = st.slider("Reduce waiting time by", 0, 100, 50, 5, format="%d%%", key=f"{key}_percent")
        st.form_submit_button("Run simulation", type="primary", icon=":material/play_arrow:", width="stretch")
    scenario = simulate_transition(analysis, selected[0], selected[1], percent)
    ui.scenario_result(scenario, summarize_scenario(analysis, scenario))
    return scenario


def case_lookup(analysis: Analysis, *, key: str, limit: int = 300) -> str | None:
    cases = analysis.cases["case_id"]
    with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
        query = st.text_input(
            "Search by order ID", key=f"{key}_query", placeholder="Search by order ID…",
            label_visibility="collapsed", width=200,
        ).strip()
        matches = cases[cases.str.contains(query, case=False, regex=False)] if query else cases
        if matches.empty:
            st.caption("No matching order")
            return None
        options = matches.head(limit).tolist()
        chosen = st.selectbox("Order", options, key=f"{key}_case", label_visibility="collapsed", width=150)
    return chosen
