"""Dashboard-level summaries derived from an Analysis.

Every number here is a plain aggregate of observed timestamps. Ratings are
rules of thumb for where to look first, not proof of a cause.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .analyzer import Analysis
from .scenario import Scenario

AVERAGE_MONTH_DAYS = 30.44

# A transition is "High" when it holds a large share of all waiting time, or
# when its slow tail is far from its typical case (P90 vs median).
HIGH_SHARE, MEDIUM_SHARE = 0.25, 0.05
HIGH_SPREAD, MEDIUM_SPREAD = 4.0, 2.5


def _rating(share: float, spread: float) -> str:
    if share >= HIGH_SHARE or spread >= HIGH_SPREAD:
        return "High"
    if share >= MEDIUM_SHARE or spread >= MEDIUM_SPREAD:
        return "Medium"
    return "OK"


def bottlenecks(analysis: Analysis, *, min_case_share: float = 0.01) -> pd.DataFrame:
    """Transitions ranked by total waiting time, with a severity rating.

    Rare paths (fewer than ``min_case_share`` of cases) are dropped so a
    handful of odd orders cannot outrank the main flow.
    """

    frame = analysis.transitions.copy()
    if frame.empty:
        return frame.assign(time_share=[], spread=[], status=[])
    frame = frame.loc[frame["cases"] >= max(1, analysis.total_cases * min_case_share)].copy()
    total = analysis.transitions["total_case_hours"].sum()
    frame["time_share"] = frame["total_case_hours"] / total if total else 0.0
    median = frame["median_hours"].where(frame["median_hours"] > 0)
    frame["spread"] = (frame["p90_hours"] / median).fillna(1.0)
    frame["status"] = [_rating(share, spread) for share, spread in zip(frame["time_share"], frame["spread"])]
    return frame.reset_index(drop=True)


@dataclass(frozen=True)
class PeriodChange:
    """Second half of the observed window compared with the first half."""

    cases: float | None
    events: float | None
    mean_cycle: float | None
    split: pd.Timestamp | None


def _change(current: float, previous: float) -> float | None:
    if not previous or pd.isna(previous) or pd.isna(current):
        return None
    return (current - previous) / previous


def period_change(analysis: Analysis) -> PeriodChange:
    cases = analysis.cases
    if len(cases) < 20:
        return PeriodChange(None, None, None, None)
    start, end = cases["first_event"].min(), cases["first_event"].max()
    if start == end:
        return PeriodChange(None, None, None, None)
    split = start + (end - start) / 2
    recent = cases["first_event"] >= split
    events = cases["event_count"]
    cycle = cases.loc[cases["completed"], ["cycle_hours"]].join(recent.rename("recent"))
    return PeriodChange(
        cases=_change(recent.sum(), (~recent).sum()),
        events=_change(events[recent].sum(), events[~recent].sum()),
        mean_cycle=_change(
            cycle.loc[cycle["recent"], "cycle_hours"].mean(),
            cycle.loc[~cycle["recent"], "cycle_hours"].mean(),
        ),
        split=split,
    )


def observed_months(analysis: Analysis) -> float:
    """Length of the window in which orders were created, in months (min. 1)."""

    if analysis.cases.empty:
        return 1.0
    span = analysis.cases["first_event"].max() - analysis.cases["first_event"].min()
    return max(span.total_seconds() / 86_400 / AVERAGE_MONTH_DAYS, 1.0)


@dataclass(frozen=True)
class ScenarioSummary:
    mean_change: float | None
    saved_per_affected_case_hours: float | None
    case_hours_per_month: float


def summarize_scenario(analysis: Analysis, scenario: Scenario) -> ScenarioSummary:
    current, adjusted = scenario.current_mean_hours, scenario.adjusted_mean_hours
    return ScenarioSummary(
        mean_change=_change(adjusted, current) if current is not None and adjusted is not None else None,
        saved_per_affected_case_hours=(
            scenario.removed_case_hours / scenario.affected_cases if scenario.affected_cases else None
        ),
        case_hours_per_month=scenario.removed_case_hours / observed_months(analysis),
    )


def resource_count(analysis: Analysis) -> int | None:
    if "resource" not in analysis.raw_events:
        return None
    values = analysis.raw_events["resource"].astype("string").str.strip()
    return int(values[values.ne("") & values.notna()].nunique())


def department_workload(analysis: Analysis) -> pd.DataFrame:
    """Waiting time before each department's events, from transition targets."""

    instances = analysis.transition_instances
    if "to_department" not in instances or instances.empty:
        return pd.DataFrame(columns=["department", "events", "cases", "median_wait_hours", "total_wait_hours", "resources"])
    frame = instances.assign(to_department=instances["to_department"].astype("string").fillna("").str.strip())
    frame = frame.loc[frame["to_department"].ne("")]
    aggregations = {
        "events": ("case_id", "size"),
        "cases": ("case_id", "nunique"),
        "median_wait_hours": ("gap_hours", "median"),
        "total_wait_hours": ("gap_hours", "sum"),
    }
    if "to_resource" in frame:
        aggregations["resources"] = ("to_resource", "nunique")
    grouped = frame.groupby("to_department").agg(**aggregations)
    return (
        grouped.reset_index()
        .rename(columns={"to_department": "department"})
        .sort_values("total_wait_hours", ascending=False)
        .reset_index(drop=True)
    )


def weekly_throughput(analysis: Analysis) -> pd.DataFrame:
    """Orders started and completed per ISO week."""

    cases = analysis.cases
    started = cases["first_event"].dt.tz_convert(None).dt.to_period("W").dt.start_time.value_counts()
    done = cases.loc[cases["completed"], "last_process_event"]
    completed = done.dt.tz_convert(None).dt.to_period("W").dt.start_time.value_counts()
    frame = pd.DataFrame({"Started": started, "Completed": completed}).fillna(0).astype(int).sort_index()
    frame.index.name = "week"
    return frame.reset_index()
