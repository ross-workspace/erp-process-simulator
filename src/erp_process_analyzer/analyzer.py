"""Deterministic, UI-independent process analytics."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

PAYMENT = "Payment Received"

TRANSITION_COLUMNS = [
    "from_activity", "to_activity", "occurrences", "cases", "mean_hours",
    "median_hours", "p90_hours", "total_case_hours",
]


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
    """A case loops back when any activity is recorded more than once."""

    return len(set(activities)) < len(activities)


def _sorted(events: pd.DataFrame) -> pd.DataFrame:
    order = ["case_id"] + [column for column in ("timestamp", "event_order", "source_row") if column in events]
    return events.sort_values(order, kind="stable", na_position="last")


def analyze(events: pd.DataFrame) -> Analysis:
    """Calculate metrics for one prepared single-order-per-case event log."""

    ordered = _sorted(events)
    case_key = ordered["case_id"].astype(str)
    position = case_key.groupby(case_key, sort=False).cumcount()

    # Everything up to and including the first payment is the process; later
    # events stay visible in raw_events but do not shape the metrics.
    is_payment = ordered["activity"].eq(PAYMENT)
    first_payment = position[is_payment].groupby(case_key[is_payment]).min()
    payment_position = case_key.map(first_payment)
    in_process = payment_position.isna() | position.le(payment_position)

    process = ordered.loc[in_process]
    process_case = case_key[in_process]
    process_ts = process["timestamp"]
    activity = process["activity"].astype(str)

    by_case = process_ts.groupby(process_case, sort=False)
    sequences = activity.groupby(process_case, sort=False).agg(tuple)
    rework = sequences.map(_has_rework)
    completed = sequences.index.isin(first_payment.index)
    first_event = by_case.min()
    last_event = by_case.max()
    cycle = (last_event - first_event).dt.total_seconds() / 3600
    event_count = case_key.groupby(case_key, sort=False).size()
    post_payment = (~in_process).groupby(case_key, sort=False).sum()
    ambiguous = (
        ordered["sequence_ambiguous"].groupby(case_key, sort=False).any()
        if "sequence_ambiguous" in ordered
        else pd.Series(False, index=event_count.index)
    )

    cases = pd.DataFrame(
        {
            "case_id": sequences.index.astype(str),
            "completed": completed,
            "cycle_hours": cycle.where(completed).to_numpy(),
            "first_event": first_event.to_numpy(),
            "last_process_event": last_event.to_numpy(),
            "event_count": event_count.reindex(sequences.index).to_numpy(),
            "process_event_count": by_case.size().to_numpy(),
            "post_payment_events": post_payment.reindex(sequences.index).astype(int).to_numpy(),
            "sequence_ambiguous": ambiguous.reindex(sequences.index).astype(bool).to_numpy(),
            "rework": rework.to_numpy(),
            "variant": sequences.to_numpy(),
        }
    )
    cases["first_event"] = pd.to_datetime(cases["first_event"], utc=True)
    cases["last_process_event"] = pd.to_datetime(cases["last_process_event"], utc=True)
    cases["cycle_hours"] = cases["cycle_hours"].astype(float)

    next_activity = activity.groupby(process_case, sort=False).shift(-1)
    next_ts = process_ts.groupby(process_case, sort=False).shift(-1)
    has_next = next_activity.notna()
    instances = pd.DataFrame(
        {
            "case_id": process_case[has_next].to_numpy(),
            "from_activity": activity[has_next].to_numpy(),
            "to_activity": next_activity[has_next].astype(str).to_numpy(),
            "gap_hours": ((next_ts[has_next] - process_ts[has_next]).dt.total_seconds() / 3600).to_numpy(),
        }
    )
    for column in ("resource", "department"):
        if column in process:
            instances[f"to_{column}"] = process[column].groupby(process_case, sort=False).shift(-1)[has_next].to_numpy()

    if instances.empty:
        transitions = pd.DataFrame(columns=TRANSITION_COLUMNS)
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

    activities = (
        pd.DataFrame({"activity": activity.to_numpy(), "case_id": process_case.to_numpy()})
        .groupby("activity", sort=False)
        .agg(cases=("case_id", "nunique"), occurrences=("case_id", "size"))
        .reset_index()
        .sort_values("cases", ascending=False, kind="stable")
        .reset_index(drop=True)
    )

    variant_counts = sequences.value_counts(sort=False)
    variants = pd.DataFrame(
        {
            "variant": variant_counts.index.tolist(),
            "cases": variant_counts.to_numpy(),
        },
        columns=["variant", "cases"],
    )
    variants["share"] = variants["cases"] / max(len(cases), 1)
    variants["rework"] = variants["variant"].map(_has_rework).astype(bool)
    variants = variants.sort_values("cases", ascending=False, kind="stable").reset_index(drop=True)

    completed_cycles = cases.loc[cases["completed"], "cycle_hours"].dropna()
    return Analysis(
        raw_events=ordered,
        process_events=process.copy(),
        cases=cases,
        transition_instances=instances,
        transitions=transitions,
        activities=activities,
        variants=variants,
        total_cases=len(cases),
        completed_cases=int(cases["completed"].sum()),
        open_cases=int((~cases["completed"]).sum()),
        post_payment_events=int((~in_process).sum()),
        rework_cases=int(cases["rework"].sum()),
        mean_cycle_hours=float(completed_cycles.mean()) if not completed_cycles.empty else None,
        median_cycle_hours=float(completed_cycles.median()) if not completed_cycles.empty else None,
    )
