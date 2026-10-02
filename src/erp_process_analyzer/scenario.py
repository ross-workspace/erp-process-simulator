"""Transparent historical timing calculation, not a capacity simulation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .analyzer import Analysis


@dataclass(frozen=True)
class Scenario:
    from_activity: str
    to_activity: str
    reduction_percent: float
    completed_cases: int
    affected_cases: int
    affected_occurrences: int
    current_mean_hours: float | None
    adjusted_mean_hours: float | None
    current_median_hours: float | None
    adjusted_median_hours: float | None
    removed_case_hours: float
    case_results: pd.DataFrame


def simulate_transition(
    analysis: Analysis,
    from_activity: str,
    to_activity: str,
    reduction_percent: float,
) -> Scenario:
    if not 0 <= reduction_percent <= 100:
        raise ValueError("reduction_percent must be between 0 and 100")

    completed = analysis.cases.loc[
        analysis.cases["completed"], ["case_id", "cycle_hours"]
    ].copy()
    matching = analysis.transition_instances.loc[
        analysis.transition_instances["from_activity"].eq(from_activity)
        & analysis.transition_instances["to_activity"].eq(to_activity)
    ]
    matching = matching.loc[matching["case_id"].isin(completed["case_id"])]
    removed_by_case = matching.groupby("case_id")["gap_hours"].sum() * (reduction_percent / 100)
    completed["removed_hours"] = completed["case_id"].map(removed_by_case).fillna(0.0)
    completed["adjusted_hours"] = (completed["cycle_hours"] - completed["removed_hours"]).clip(lower=0)

    return Scenario(
        from_activity=from_activity,
        to_activity=to_activity,
        reduction_percent=reduction_percent,
        completed_cases=len(completed),
        affected_cases=int(completed["removed_hours"].gt(0).sum()),
        affected_occurrences=len(matching),
        current_mean_hours=float(completed["cycle_hours"].mean()) if len(completed) else None,
        adjusted_mean_hours=float(completed["adjusted_hours"].mean()) if len(completed) else None,
        current_median_hours=float(completed["cycle_hours"].median()) if len(completed) else None,
        adjusted_median_hours=float(completed["adjusted_hours"].median()) if len(completed) else None,
        removed_case_hours=float(completed["removed_hours"].sum()),
        case_results=completed,
    )
