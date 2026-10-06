from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

from erp_process_analyzer import DataValidationError, analyze, load_events, simulate_transition
from erp_process_analyzer.generator import generate_events

FIXTURE = Path(__file__).parent / "fixtures" / "golden.csv"


def test_golden_analytics_and_scenario() -> None:
    events, report = load_events(FIXTURE)
    result = analyze(events)

    assert report.rows == 12
    assert report.cases == 3
    assert result.total_cases == 3
    assert result.completed_cases == 2
    assert result.open_cases == 1
    assert len(result.variants) == 3
    assert result.rework_cases == 1
    assert result.mean_cycle_hours == 10
    assert result.median_cycle_hours == 10

    edge = result.transitions.loc[
        result.transitions["from_activity"].eq("Order Approved")
        & result.transitions["to_activity"].eq("Picking Started")
    ].iloc[0]
    assert edge["cases"] == 2
    assert edge["occurrences"] == 2
    assert edge["median_hours"] == 3

    scenario = simulate_transition(result, "Order Approved", "Picking Started", 50)
    assert scenario.affected_cases == 2
    assert scenario.adjusted_mean_hours == 8.5
    assert scenario.adjusted_median_hours == 8.5
    assert scenario.removed_case_hours == 3
    assert scenario.case_results.set_index("case_id")["adjusted_hours"].to_dict() == {"A": 8, "B": 9}


def test_shuffle_does_not_change_metrics_for_distinct_timestamps() -> None:
    events, _ = load_events(FIXTURE)
    shuffled = events.sample(frac=1, random_state=7)
    original = analyze(events)
    reordered = analyze(shuffled)
    pd.testing.assert_series_equal(
        original.cases.set_index("case_id")["cycle_hours"].sort_index(),
        reordered.cases.set_index("case_id")["cycle_hours"].sort_index(),
    )
    assert original.variants["cases"].tolist() == reordered.variants["cases"].tolist()


def test_import_rejects_bad_rows_with_source_line() -> None:
    csv = StringIO("case_id,activity,timestamp\nA,Order Created,not-a-date\n")
    with pytest.raises(DataValidationError, match="CSV row 2"):
        load_events(csv)


def test_ties_are_reported_and_event_order_is_respected() -> None:
    csv = StringIO(
        "case_id,activity,timestamp,event_order\n"
        "A,Order Approved,2026-01-05T09:00:00Z,2\n"
        "A,Order Created,2026-01-05T09:00:00Z,1\n"
    )
    events, report = load_events(csv)
    assert report.tied_timestamp_rows == 2
    assert report.ambiguous_cases == 0
    assert events["activity"].tolist() == ["Order Created", "Order Approved"]


def test_post_payment_events_are_visible_but_outside_process() -> None:
    csv = StringIO(
        "case_id,activity,timestamp\n"
        "A,Order Created,2026-01-05T09:00:00Z\n"
        "A,Payment Received,2026-01-05T10:00:00Z\n"
        "A,Reminder Sent,2026-01-05T11:00:00Z\n"
    )
    events, _ = load_events(csv)
    result = analyze(events)
    assert result.post_payment_events == 1
    assert len(result.raw_events) == 3
    assert len(result.process_events) == 2
    assert result.mean_cycle_hours == 1


def test_generator_is_deterministic_and_scenarios_stay_bounded() -> None:
    first = generate_events(cases=40, seed=42, profile="messy")
    second = generate_events(cases=40, seed=42, profile="messy")
    pd.testing.assert_frame_equal(first, second)
    events, _ = load_events(StringIO(first.to_csv(index=False)))
    result = analyze(events)
    edge = result.transitions.iloc[0]
    unchanged = simulate_transition(result, edge["from_activity"], edge["to_activity"], 0)
    removed = simulate_transition(result, edge["from_activity"], edge["to_activity"], 100)
    assert unchanged.adjusted_mean_hours == pytest.approx(unchanged.current_mean_hours)
    assert removed.case_results["adjusted_hours"].ge(0).all()


@pytest.mark.parametrize("profile", ["clean", "messy", "warehouse", "manufacturing", "retail"])
def test_every_demo_profile_imports_and_analyzes(profile: str) -> None:
    frame = generate_events(cases=300, seed=1, profile=profile)
    events, report = load_events(StringIO(frame.to_csv(index=False)))
    result = analyze(events)
    assert report.cases == 300
    assert result.completed_cases > 0
    assert not result.transitions.empty


def test_manufacturing_quality_loops_count_as_rework() -> None:
    events, _ = load_events(StringIO(generate_events(cases=400, seed=3, profile="manufacturing").to_csv(index=False)))
    result = analyze(events)
    loops = result.transitions.loc[
        result.transitions["from_activity"].eq("Quality Check")
        & result.transitions["to_activity"].eq("Production Started")
    ]
    assert not loops.empty
    assert result.rework_cases >= int(loops["cases"].iloc[0])


def test_retail_returns_stay_outside_the_process() -> None:
    events, _ = load_events(StringIO(generate_events(cases=400, seed=3, profile="retail").to_csv(index=False)))
    result = analyze(events)
    assert result.post_payment_events > 0
    assert "Return Requested" not in set(result.activities["activity"])
    assert "Return Requested" in set(result.raw_events["activity"])


def test_insights_on_golden_fixture() -> None:
    from erp_process_analyzer.insights import bottlenecks, department_workload, summarize_scenario

    events, _ = load_events(FIXTURE)
    result = analyze(events)
    ranked = bottlenecks(result)
    assert ranked["time_share"].sum() == pytest.approx(1.0)
    assert set(ranked["status"]) <= {"High", "Medium", "OK"}
    # Picking → Payment holds 10 of 25 elapsed hours.
    top = ranked.iloc[0]
    assert (top["from_activity"], top["to_activity"]) == ("Picking Started", "Payment Received")
    assert top["status"] == "High"
    summary = summarize_scenario(result, simulate_transition(result, "Order Approved", "Picking Started", 50))
    assert summary.saved_per_affected_case_hours == 1.5
    assert summary.mean_change == pytest.approx(-0.15)
    assert department_workload(result).empty
