"""HTML fragments and formatting used by several pages.

Native Streamlit widgets handle all interaction; these helpers only render
dense read-only tables and cards that would otherwise need many elements.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from erp_process_analyzer import Analysis, Scenario
from erp_process_analyzer.insights import PeriodChange, ScenarioSummary, resource_count

from .state import money

CSS = Path(__file__).with_name("style.css")

SHORT_NAMES = {
    "Order Created": "Created",
    "Order Approved": "Approved",
    "Order Edited": "Edited",
    "Order Cancelled": "Cancelled",
    "Material Reserved": "Material",
    "Production Started": "Production",
    "Quality Check": "Quality check",
    "Picking Started": "Picking",
    "Packed": "Packed",
    "Shipped": "Shipped",
    "Invoice Created": "Invoice",
    "Payment Received": "Payment",
}

ICONS = {
    "cases": '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "events": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/>',
    "activities": '<rect width="8" height="8" x="3" y="3" rx="2"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><rect width="8" height="8" x="13" y="13" rx="2"/>',
    "resources": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "variants": '<circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9"/><path d="M12 12v3"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "repeat": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "spread": '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>',
}


def inject_css() -> None:
    st.html(f"<style>{CSS.read_text()}</style>")


def html(fragment: str) -> None:
    """Render trusted, pre-escaped HTML. st.html sanitizes SVG away, markdown keeps it."""

    st.markdown(fragment, unsafe_allow_html=True)


def icon(name: str, size: int = 20) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'
    )


def short(activity: str) -> str:
    return SHORT_NAMES.get(activity, activity)


def duration(hours: float | None, *, long: bool = False) -> str:
    if hours is None or pd.isna(hours):
        return "—"
    if hours < 1:
        return f"{hours * 60:.0f} min"
    if hours < 24:
        return f"{hours:.1f} {'hours' if long else 'h'}"
    days = hours / 24
    return f"{days:.1f} days" if days < 10 else f"{days:.0f} days"


def percent(value: float | None, digits: int = 0) -> str:
    return "—" if value is None or pd.isna(value) else f"{value:.{digits}%}"


def _delta(change: float | None, *, up_is_good: bool, title: str) -> str:
    if change is None or pd.isna(change) or abs(change) < 0.005:
        return ""
    good = (change > 0) == up_is_good
    arrow = "↑" if change > 0 else "↓"
    return f'<span class="delta {"good" if good else "bad"}" title="{escape(title)}">{arrow} {abs(change):.0%}</span>'


def kpi_cards(analysis: Analysis, change: PeriodChange) -> None:
    resources = resource_count(analysis)
    period = (
        f"Orders created from {change.split:%d %b %Y} compared with earlier orders"
        if change.split is not None
        else ""
    )
    cards = [
        ("cases", "Cases (orders)", f"{analysis.total_cases:,}", _delta(change.cases, up_is_good=True, title=period),
         f"{analysis.completed_cases:,} paid · {analysis.open_cases:,} open"),
        ("events", "Events", f"{len(analysis.raw_events):,}", _delta(change.events, up_is_good=True, title=period),
         "Total recorded events"),
        ("activities", "Activities", f"{len(analysis.activities):,}", "", "Unique process activities"),
        ("resources", "Resources", f"{resources:,}" if resources is not None else "—", "", "People / systems"),
        ("clock", "Average cycle time", duration(analysis.mean_cycle_hours, long=True),
         _delta(change.mean_cycle, up_is_good=False, title=period), "From order to payment"),
        ("variants", "Process variants", f"{len(analysis.variants):,}", "", "Unique process flows"),
    ]
    markup = "".join(
        f'<div class="kpi"><div class="kpi-icon">{icon(key, 22)}</div><div class="kpi-body">'
        f'<div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{escape(value)}{delta}</div>'
        f'<div class="kpi-note">{escape(note)}</div></div></div>'
        for key, label, value, delta, note in cards
    )
    html(f'<div class="kpi-grid">{markup}</div>')


def insights(analysis: Analysis, ranked: pd.DataFrame) -> None:
    rows = []
    if len(analysis.variants):
        top = analysis.variants.iloc[0]
        rows.append(("link", "blue", "Most common variant", percent(top["share"]),
                     f"{len(top['variant'])} steps · {top['cases']:,} orders follow it"))
    rows.append(("repeat", "red", "Rework rate", percent(analysis.rework_cases / max(analysis.total_cases, 1)),
                 "Orders that loop back to an earlier step"))
    if len(ranked):
        top = ranked.iloc[0]
        rows.append(("alert", "red", "Biggest bottleneck", f"{short(top['from_activity'])} → {short(top['to_activity'])}",
                     f"Median {duration(top['median_hours'])} · {top['time_share']:.0%} of all waiting time"))
        spread = ranked.sort_values("spread", ascending=False).iloc[0]
        rows.append(("spread", "blue", "Least predictable step",
                     f"{short(spread['from_activity'])} → {short(spread['to_activity'])}",
                     f"Median {duration(spread['median_hours'])} | P90 {duration(spread['p90_hours'])}"))
    markup = "".join(
        f'<div class="insight"><div class="insight-icon {tone}">{icon(key, 20)}</div><div>'
        f'<div class="insight-label">{escape(label)}</div><div class="insight-value">{escape(value)}</div>'
        f'<div class="insight-note">{escape(note)}</div></div></div>'
        for key, tone, label, value, note in rows
    )
    html(f'<div class="insights">{markup}</div>')


STATUS_BADGE = {"High": ("high", "▲ High"), "Medium": ("medium", "▲ Medium"), "OK": ("ok", "✓ OK")}


def bottleneck_table(ranked: pd.DataFrame, limit: int = 5) -> None:
    if ranked.empty:
        st.info("At least two events in a case are needed for transitions.")
        return
    rows = []
    for number, row in enumerate(ranked.head(limit).itertuples(index=False), start=1):
        css, label = STATUS_BADGE[row.status]
        hot = ' class="hot"' if row.status == "High" else ""
        title = f"{row.from_activity} → {row.to_activity}: {row.time_share:.1%} of waiting time, P90 is {row.spread:.1f}× the median"
        rows.append(
            f'<tr title="{escape(title)}"><td class="num">{number}</td>'
            f'<td class="wrap">{escape(short(row.from_activity))} → {escape(short(row.to_activity))}</td>'
            f"<td{hot}>{duration(row.median_hours)}</td><td{hot}>{duration(row.p90_hours)}</td>"
            f'<td>{row.cases:,}</td><td><span class="badge {css}">{label}</span></td></tr>'
        )
    html(
        '<table class="tbl"><thead><tr><th>#</th><th>Transition</th><th>Median</th><th>P90</th>'
        f'<th>Cases</th><th>Status</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )


def variant_table(analysis: Analysis, limit: int = 5) -> None:
    variants = analysis.variants
    if variants.empty:
        st.info("No process variants in this log.")
        return
    top_share = variants["share"].max()
    rows = []

    def row(number: str, flow: str, full: str, cases: int, share: float) -> str:
        width = 100 * share / top_share if top_share else 0
        return (
            f'<tr title="{escape(full)}"><td class="num">{number}</td><td class="flow">'
            f'<div class="flow-text">{escape(flow)}</div><div class="bar"><span style="width:{width:.1f}%"></span></div></td>'
            f"<td>{cases:,}</td><td>{share:.0%}</td></tr>"
        )

    for number, variant in enumerate(variants.head(limit).itertuples(index=False), start=1):
        sequence = variant.variant
        rows.append(row(str(number), " → ".join(short(step) for step in sequence), " → ".join(sequence), variant.cases, variant.share))
    rest = variants.iloc[limit:]
    if len(rest):
        rows.append(row("", f"Other variants ({len(rest):,})", "All remaining variants", int(rest["cases"].sum()), float(rest["share"].sum())))
    html(
        '<table class="tbl variants"><thead><tr><th>#</th><th>Process flow</th><th>Cases</th><th>%</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def scenario_result(scenario: Scenario, summary: ScenarioSummary) -> None:
    change = (
        f'<span class="good">↓ {abs(summary.mean_change):.1%}</span>'
        if summary.mean_change is not None and summary.mean_change < 0
        else "–"
    )
    median_change = "–"
    if scenario.current_median_hours and scenario.adjusted_median_hours is not None:
        delta = (scenario.adjusted_median_hours - scenario.current_median_hours) / scenario.current_median_hours
        if delta < -0.0005:
            median_change = f'<span class="good">↓ {abs(delta):.1%}</span>'
    rows = [
        ("Average cycle time", duration(scenario.current_mean_hours, long=True), duration(scenario.adjusted_mean_hours, long=True), change),
        ("Median cycle time", duration(scenario.current_median_hours, long=True), duration(scenario.adjusted_median_hours, long=True), median_change),
        ("Time saved per affected order", "", duration(summary.saved_per_affected_case_hours, long=True), "–"),
        ("Case-hours saved per month", "", f"{summary.case_hours_per_month:,.0f} h", "–"),
    ]
    body = "".join(
        f"<tr><td>{escape(metric)}</td><td>{escape(current)}</td><td><b>{escape(simulated)}</b></td><td>{delta}</td></tr>"
        for metric, current, simulated, delta in rows
    )
    html(
        '<div class="sim-result"><div class="sim-title">Simulation result</div><table class="tbl compact">'
        "<thead><tr><th>Metric</th><th>Current</th><th>Simulated</th><th>Change</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def case_events(analysis: Analysis, case_id: str) -> pd.DataFrame:
    frame = analysis.raw_events.loc[analysis.raw_events["case_id"].astype(str).eq(case_id)].copy()
    gap = (frame["timestamp"].shift(-1) - frame["timestamp"]).dt.total_seconds() / 3600
    out = pd.DataFrame(
        {
            "Timestamp (UTC)": frame["timestamp"].dt.strftime("%Y-%m-%d %H:%M"),
            "Activity": frame["activity"],
        }
    )
    for column, title in (("resource", "Resource"), ("department", "Department")):
        if column in frame:
            out[title] = frame[column]
    out["Duration to next"] = [_compact_gap(value) for value in gap]
    if "order_value" in frame:
        out["Order value"] = frame["order_value"].map(money)
    return out.reset_index(drop=True)


def _compact_gap(hours: float) -> str:
    if pd.isna(hours):
        return "–"
    minutes = round(hours * 60)
    days, rest = divmod(minutes, 24 * 60)
    hrs, mins = divmod(rest, 60)
    if days >= 3:
        return f"{days}d" if hrs == 0 else f"{days}d {hrs}h"
    if days:
        return f"{days}d {hrs}h"
    return f"{hrs}h {mins:02d}m" if hrs else f"{mins}m"


def case_table(frame: pd.DataFrame) -> None:
    head = "".join(f"<th>{escape(column)}</th>" for column in frame.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
        for row in frame.itertuples(index=False)
    )
    html(f'<table class="tbl compact case"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')


def legend() -> None:
    html(
        '<div class="legend"><span><i class="line strong"></i>More common</span>'
        '<span><i class="line weak"></i>Less common</span>'
        '<span><i class="line loop"></i>Rework / loop</span></div>'
    )


def panel_header(title: str, help: str, link: str | None = None, link_label: str = "View all") -> None:
    if link is None:
        st.subheader(title, help=help, anchor=False)
        return
    left, right = st.columns([1.9, 1], vertical_alignment="center")
    left.subheader(title, help=help, anchor=False)
    with right.container(horizontal=True, horizontal_alignment="right"):
        st.page_link(link, label=link_label, icon=":material/arrow_forward:", icon_position="right")
