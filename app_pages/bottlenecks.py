import altair as alt
import streamlit as st

from dashboard import components as ui
from dashboard import state
from erp_process_analyzer.insights import bottlenecks, department_workload, weekly_throughput

source = state.current_source()
analysis = source.analysis
ranked = bottlenecks(analysis, min_case_share=0)

high = ranked.loc[ranked["status"].eq("High")]
with st.container(horizontal=True):
    st.metric("Transitions rated High", f"{len(high):,}", border=True)
    st.metric(
        "Waiting time in High transitions",
        ui.percent(high["time_share"].sum()) if len(high) else "—",
        border=True,
    )
    st.metric("Total elapsed case-hours", f"{analysis.transitions['total_case_hours'].sum():,.0f} h", border=True)

with st.container(border=True, key="card-ranking"):
    st.subheader(
        "Ranking", anchor=False,
        help="High: over 25% of all waiting time or P90 ≥ 4× median. Medium: over 5% or P90 ≥ 2.5× median.",
    )
    table = ranked.assign(
        transition=ranked["from_activity"] + " → " + ranked["to_activity"],
        median=ranked["median_hours"].map(ui.duration),
        p90=ranked["p90_hours"].map(ui.duration),
    )
    st.dataframe(
        table[["transition", "status", "median", "p90", "spread", "cases", "time_share"]],
        hide_index=True,
        column_config={
            "transition": st.column_config.TextColumn("Transition", width="large"),
            "status": "Status",
            "median": "Median",
            "p90": "P90",
            "spread": st.column_config.NumberColumn("P90 ÷ median", format="%.1f×"),
            "cases": st.column_config.NumberColumn("Orders", format="localized"),
            "time_share": st.column_config.ProgressColumn("Share of waiting time", format="percent", min_value=0, max_value=1),
        },
    )

chart_col, dept_col = st.columns([1.4, 1])
with chart_col.container(border=True, key="card-spread", height="stretch"):
    st.subheader("Typical vs slow orders", anchor=False, help="Bars run from the median to the 90th percentile wait, in hours.")
    top = ranked.head(10).assign(label=lambda f: f["from_activity"].map(ui.short) + " → " + f["to_activity"].map(ui.short))
    order = top["label"].tolist()
    base = alt.Chart(top).encode(y=alt.Y("label:N", sort=order, title=None, axis=None))
    chart = base.mark_rule(strokeWidth=6, color="#c9d3f5").encode(
        x=alt.X("median_hours:Q", title="Hours (log scale)", scale=alt.Scale(type="log")), x2="p90_hours:Q",
    ) + base.mark_point(filled=True, size=90, color="#3d5afe").encode(
        x="median_hours:Q", tooltip=[alt.Tooltip("label:N", title="Transition"), alt.Tooltip("median_hours:Q", title="Median h", format=".1f")],
    ) + base.mark_point(filled=True, size=90, color="#e5484d").encode(
        x="p90_hours:Q", tooltip=[alt.Tooltip("label:N", title="Transition"), alt.Tooltip("p90_hours:Q", title="P90 h", format=".1f")],
    )
    names = base.mark_text(align="left", baseline="bottom", dy=-6, fontSize=11, color="#3d4a63").encode(
        x="median_hours:Q", text="label:N",
    )
    st.altair_chart((chart + names).properties(height=380))
    st.caption(":blue[●] median  :red[●] 90th percentile")

with dept_col.container(border=True, key="card-departments", height="stretch"):
    st.subheader(
        "Waiting by receiving team", anchor=False,
        help="Time before each department's events, i.e. how long work sat before that team recorded its step.",
    )
    workload = department_workload(analysis)
    if workload.empty:
        st.info("Add a `department` column to the event log to see this breakdown.")
    else:
        workload["median"] = workload["median_wait_hours"].map(ui.duration)
        workload["share"] = workload["total_wait_hours"] / workload["total_wait_hours"].sum()
        columns = ["department", "median", "events", "share"] + (["resources"] if "resources" in workload else [])
        st.dataframe(
            workload[columns],
            hide_index=True,
            column_config={
                "department": "Department",
                "median": "Median wait",
                "events": st.column_config.NumberColumn("Events", format="localized"),
                "share": st.column_config.ProgressColumn("Share of waiting", format="percent", min_value=0, max_value=1),
                "resources": "People",
            },
        )

with st.container(border=True, key="card-throughput"):
    st.subheader("Weekly throughput", anchor=False, help="Orders created vs. orders paid, per calendar week (UTC).")
    weekly = weekly_throughput(analysis).melt("week", var_name="Orders", value_name="count")
    st.altair_chart(
        alt.Chart(weekly)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("week:T", title=None, axis=alt.Axis(format="%d %b")),
            y=alt.Y("count:Q", title="Orders per week"),
            color=alt.Color("Orders:N", scale=alt.Scale(range=["#2f9e5b", "#3d5afe"]), legend=alt.Legend(orient="top", title=None)),
            tooltip=[alt.Tooltip("week:T", title="Week of", format="%d %b %Y"), "Orders:N", alt.Tooltip("count:Q", title="Orders")],
        )
        .properties(height=260)
    )
    st.caption("Started drops after the last order-creation date in the log; completions keep arriving until the last payment.")
