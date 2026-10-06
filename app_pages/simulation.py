import altair as alt
import pandas as pd
import streamlit as st

from dashboard import components as ui
from dashboard import panels, state
from erp_process_analyzer import simulate_transition
from erp_process_analyzer.insights import bottlenecks

source = state.current_source()
analysis = source.analysis
ranked = bottlenecks(analysis)

controls, charts = st.columns([1, 1.7])
with controls.container(border=True, key="card-sim-full", height="stretch"):
    st.subheader("Scenario", anchor=False)
    scenario = panels.simulation(analysis, ranked, key="simulation")

if scenario is not None:
    with charts.container(border=True, key="card-sim-dist", height="stretch"):
        st.subheader(
            "Cycle time distribution", anchor=False,
            help="Completed orders, current vs. simulated. Days, capped at the 99th percentile for readability.",
        )
        results = scenario.case_results
        cap = results["cycle_hours"].quantile(0.99) / 24
        long = pd.concat(
            [
                pd.DataFrame({"days": results["cycle_hours"] / 24, "Series": "Current"}),
                pd.DataFrame({"days": results["adjusted_hours"] / 24, "Series": "Simulated"}),
            ]
        )
        long = long.loc[long["days"] <= cap]
        chart = (
            alt.Chart(long)
            .mark_area(opacity=0.45, interpolate="monotone")
            .encode(
                x=alt.X("days:Q", bin=alt.Bin(maxbins=60), title="Cycle time (days)"),
                y=alt.Y("count():Q", stack=None, title="Orders"),
                color=alt.Color("Series:N", scale=alt.Scale(range=["#9aa8c7", "#2f9e5b"]), legend=alt.Legend(orient="top", title=None)),
            )
            .properties(height=250)
        )
        st.altair_chart(chart)

        st.subheader(
            "Sensitivity", anchor=False,
            help="Average cycle time of completed orders if the selected wait were cut by 0–100%.",
        )
        curve = pd.DataFrame(
            [
                {
                    "Reduction (%)": percent,
                    "Average cycle (days)": simulate_transition(
                        analysis, scenario.from_activity, scenario.to_activity, percent
                    ).adjusted_mean_hours / 24,
                }
                for percent in range(0, 101, 10)
            ]
        )
        st.altair_chart(
            alt.Chart(curve)
            .mark_line(point=True, color="#3d5afe")
            .encode(
                x=alt.X("Reduction (%):Q"),
                y=alt.Y("Average cycle (days):Q", scale=alt.Scale(zero=False)),
                tooltip=["Reduction (%)", alt.Tooltip("Average cycle (days):Q", format=".2f")],
            )
            .properties(height=200)
        )

with st.expander("How the simulation works", icon=":material/info:"):
    st.markdown(
        f"""
- For every **completed** order, each occurrence of the selected transition loses the chosen share of its observed
  waiting time; later events shift earlier by the same amount.
- Mean and median cycle times are then recomputed. Open orders ({analysis.open_cases:,}) are excluded.
- *Case-hours* are elapsed order time, not labour hours or money. Per month = total ÷ the
  months in which orders were created.
- Not modelled: staffing and capacity, queues, parallel work, payment terms, and how people would change behaviour.
"""
    )
