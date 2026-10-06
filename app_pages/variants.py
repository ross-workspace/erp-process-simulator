import pandas as pd
import streamlit as st

from dashboard import components as ui
from dashboard import state

source = state.current_source()
analysis = source.analysis
variants = analysis.variants

with st.container(horizontal=True):
    st.metric("Unique variants", f"{len(variants):,}", border=True)
    if len(variants):
        st.metric("Orders on the main path", ui.percent(variants.iloc[0]["share"], 1), border=True)
        covered = (variants["share"].cumsum() < 0.95).sum() + 1
        st.metric("Variants covering 95% of orders", f"{min(covered, len(variants)):,}", border=True)
    st.metric("Rework rate", ui.percent(analysis.rework_cases / max(analysis.total_cases, 1), 1), border=True)

with st.container(border=True, key="card-variant-list"):
    st.subheader("All variants", anchor=False, help="Select a row to inspect that variant's steps and orders.")
    table = variants.assign(
        number=range(1, len(variants) + 1),
        flow=variants["variant"].map(lambda steps: " → ".join(ui.short(step) for step in steps)),
        steps=variants["variant"].map(len),
    )
    selection = st.dataframe(
        table[["number", "flow", "steps", "cases", "share", "rework"]],
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="variant_table",
        column_config={
            "number": st.column_config.NumberColumn("#", width="small"),
            "flow": st.column_config.TextColumn("Process flow", width="large"),
            "steps": "Steps",
            "cases": st.column_config.NumberColumn("Orders", format="localized"),
            "share": st.column_config.ProgressColumn("Share", format="percent", min_value=0, max_value=1),
            "rework": st.column_config.CheckboxColumn("Loops back"),
        },
    )

picked = selection.selection.rows[0] if selection.selection.rows else 0
if len(variants):
    chosen = variants.iloc[picked]
    members = analysis.cases.loc[analysis.cases["variant"].map(lambda steps: steps == chosen["variant"])]
    detail, cohort = st.columns([1.3, 1])
    with detail.container(border=True, key="card-variant-detail", height="stretch"):
        st.subheader(f"Variant {picked + 1}", anchor=False)
        st.markdown(" → ".join(f"`{step}`" for step in chosen["variant"]))
        completed = members.loc[members["completed"], "cycle_hours"]
        with st.container(horizontal=True):
            st.metric("Orders", f"{len(members):,}")
            st.metric("Paid", f"{int(members['completed'].sum()):,}")
            st.metric("Median cycle", ui.duration(completed.median() if len(completed) else None, long=True))
        st.caption("Example orders: " + ", ".join(members["case_id"].head(8)))

    with cohort.container(border=True, key="card-rework", height="stretch"):
        st.subheader("What rework costs", anchor=False, help="Completed orders with and without a loop back to an earlier step.")
        done = analysis.cases.loc[analysis.cases["completed"]]
        if done.empty or done["rework"].nunique() < 2:
            st.info("This log has no completed orders with rework to compare.")
        else:
            comparison = done.groupby("rework")["cycle_hours"].agg(["size", "median", "mean"])
            with_rework, without = comparison.loc[True], comparison.loc[False]
            st.metric(
                "Median cycle with rework",
                ui.duration(with_rework["median"], long=True),
                f"{ui.duration(with_rework['median'] - without['median'], long=True)} vs. without",
                delta_color="inverse",
            )
            st.dataframe(
                pd.DataFrame(
                    {
                        "Cohort": ["Without rework", "With rework"],
                        "Orders": [int(without["size"]), int(with_rework["size"])],
                        "Median cycle": [ui.duration(without["median"]), ui.duration(with_rework["median"])],
                        "Mean cycle": [ui.duration(without["mean"]), ui.duration(with_rework["mean"])],
                    }
                ),
                hide_index=True,
            )
            st.caption("An observed association: other differences between these orders may also explain the gap.")
