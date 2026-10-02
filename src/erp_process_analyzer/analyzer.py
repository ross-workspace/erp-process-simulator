"""Deterministic, UI-independent process analytics."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import pandas as pd

PAYMENT = "Payment Received"


@dataclass(frozen=True)
class Analysis:
    raw_events: pd.DataFrame
    process_events: pd.DataFrame
    cases: pd.DataFrame
    transition_instances: pd.DataFrame
    transitions: pd.DataFrame
    activities: pd.DataFrame
    variants: pd.DataFrame
    total_cases: int
    completed_cases: int
    open_cases: int
    post_payment_events: int
    rework_cases: int
    mean_cycle_hours: float | None
    median_cycle_hours: float | None


def _has_rework(activities: tuple[str, ...]) -> bool:
    state = 0
    for activity in activities:
        if state == 0 and activity == "Order Approved":
            state = 1
        elif state == 1 and activity == "Order Edited":
            state = 2
        elif state == 2 and activity == "Order Approved":
            return True
    return False


def analyze(events: pd.DataFrame) -> Analysis:
    """Calculate metrics for one prepared single-order-per-case event log."""

    case_rows: list[dict] = []
    transition_rows: list[dict] = []
    process_indices: list[int] = []
    activity_cases: dict[str, set[str]] = defaultdict(set)
    activity_occurrences: Counter[str] = Counter()
    variant_cases: dict[tuple[str, ...], list[str]] = defaultdict(list)
    post_payment_count = 0

    for case_id, group in events.groupby("case_id", sort=False, dropna=False):
        group = group.sort_values(
            [column for column in ("timestamp", "event_order", "source_row") if column in group],
            kind="stable",
            na_position="last",
        )
        payments = group.index[group["activity"].eq(PAYMENT)].tolist()
        completed = bool(payments)
        if completed:
            payment_position = group.index.get_loc(payments[0])
            process_group = group.iloc[: payment_position + 1]
        else:
            process_group = group
        post_payment = len(group) - len(process_group)
        post_payment_count += post_payment
        process_indices.extend(process_group.index.tolist())

        activities = tuple(str(activity) for activity in process_group["activity"].tolist())
        variant_cases[activities].append(str(case_id))
        timestamps = process_group["timestamp"].tolist()
        cycle_hours = (
            (timestamps[-1] - timestamps[0]).total_seconds() / 3600
            if completed and timestamps
            else None
        )
        rework = _has_rework(activities)
        case_rows.append(
            {
                "case_id": str(case_id),
                "completed": completed,
                "cycle_hours": cycle_hours,
                "first_event": timestamps[0],
                "last_process_event": timestamps[-1],
                "event_count": len(group),
                "process_event_count": len(process_group),
                "post_payment_events": post_payment,
                "sequence_ambiguous": bool(group["sequence_ambiguous"].any()) if "sequence_ambiguous" in group else False,
                "rework": rework,
                "variant": activities,
            }
        )

        for activity in activities:
            activity_occurrences[activity] += 1
            activity_cases[activity].add(str(case_id))
        for index in range(len(activities) - 1):
            transition_rows.append(
                {
                    "case_id": str(case_id),
                    "from_activity": activities[index],
                    "to_activity": activities[index + 1],
                    "gap_hours": (timestamps[index + 1] - timestamps[index]).total_seconds() / 3600,
                }
            )

    cases = pd.DataFrame(case_rows)
    instances = pd.DataFrame(
        transition_rows,
        columns=["case_id", "from_activity", "to_activity", "gap_hours"],
    )
    if instances.empty:
        transitions = pd.DataFrame(
            columns=[
                "from_activity", "to_activity", "occurrences", "cases", "mean_hours",
                "median_hours", "p90_hours", "total_case_hours",
            ]
        )
    else:
        transitions = (
            instances.groupby(["from_activity", "to_activity"], sort=False)
            .agg(
                occurrences=("case_id", "size"),
                cases=("case_id", "nunique"),
                mean_hours=("gap_hours", "mean"),
                median_hours=("gap_hours", "median"),
                p90_hours=("gap_hours", lambda values: values.quantile(0.9)),
                total_case_hours=("gap_hours", "sum"),
            )
            .reset_index()
            .sort_values("total_case_hours", ascending=False, kind="stable")
            .reset_index(drop=True)
        )

    activities = pd.DataFrame(
        [
            {"activity": name, "cases": len(activity_cases[name]), "occurrences": count}
            for name, count in activity_occurrences.items()
        ],
        columns=["activity", "cases", "occurrences"],
    )
    if not activities.empty:
        activities = activities.sort_values("cases", ascending=False, kind="stable").reset_index(drop=True)

    variants = pd.DataFrame(
        [
            {"variant": sequence, "cases": len(ids), "share": len(ids) / len(cases), "rework": _has_rework(sequence)}
            for sequence, ids in variant_cases.items()
        ],
        columns=["variant", "cases", "share", "rework"],
    )
    if not variants.empty:
        variants = variants.sort_values("cases", ascending=False, kind="stable").reset_index(drop=True)

    completed_cycles = cases.loc[cases["completed"], "cycle_hours"].dropna()
    return Analysis(
        raw_events=events,
        process_events=events.loc[process_indices].copy(),
        cases=cases,
        transition_instances=instances,
        transitions=transitions,
        activities=activities,
        variants=variants,
        total_cases=len(cases),
        completed_cases=int(cases["completed"].sum()),
        open_cases=int((~cases["completed"]).sum()),
        post_payment_events=post_payment_count,
        rework_cases=int(cases["rework"].sum()),
        mean_cycle_hours=float(completed_cycles.mean()) if not completed_cycles.empty else None,
        median_cycle_hours=float(completed_cycles.median()) if not completed_cycles.empty else None,
    )
