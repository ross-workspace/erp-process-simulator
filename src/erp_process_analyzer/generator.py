"""Reproducible synthetic Order-to-Cash logs for the public demo.

Each profile describes a different kind of company so the same analysis can be
shown against distinct process shapes: a B2B distributor with approval
rework, a make-to-order manufacturer with quality loops, and a fast retail
fulfilment flow with returns after payment.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ORDER_TO_CASH = (
    "Order Created",
    "Order Approved",
    "Picking Started",
    "Packed",
    "Shipped",
    "Invoice Created",
    "Payment Received",
)

MAKE_TO_ORDER = (
    "Order Created",
    "Order Approved",
    "Material Reserved",
    "Production Started",
    "Quality Check",
    "Packed",
    "Shipped",
    "Invoice Created",
    "Payment Received",
)

DEPARTMENTS = {
    "Order Created": "Sales",
    "Order Approved": "Management",
    "Order Edited": "Sales",
    "Material Reserved": "Planning",
    "Production Started": "Production",
    "Quality Check": "Quality",
    "Picking Started": "Warehouse",
    "Packed": "Warehouse",
    "Shipped": "Warehouse",
    "Invoice Created": "Accounting",
    "Payment Received": "Finance",
    "Order Cancelled": "Sales",
    "Return Requested": "Customer Service",
}

# Median hours since the previous event, before profile-specific delays.
BASE_GAP_HOURS = {
    "Order Approved": 1.5,
    "Order Edited": 1.0,
    "Material Reserved": 6.0,
    "Production Started": 20.0,
    "Quality Check": 30.0,
    "Picking Started": 5.5,
    "Packed": 2.0,
    "Shipped": 1.2,
    "Invoice Created": 3.0,
    "Payment Received": 120.0,
    "Order Cancelled": 30.0,
    "Return Requested": 96.0,
}


@dataclass(frozen=True)
class Profile:
    activities: tuple[str, ...]
    spread: float = 0.55
    order_value_median: float = 24_000
    staff_per_department: int = 8
    gap_overrides: dict[str, float] = field(default_factory=dict)


PROFILES = {
    "clean": Profile(ORDER_TO_CASH, spread=0.36),
    "messy": Profile(ORDER_TO_CASH),
    "warehouse": Profile(ORDER_TO_CASH),
    "manufacturing": Profile(
        MAKE_TO_ORDER,
        spread=0.5,
        order_value_median=185_000,
        staff_per_department=6,
        gap_overrides={"Payment Received": 24 * 30, "Packed": 4.0},
    ),
    "retail": Profile(
        ORDER_TO_CASH,
        spread=0.5,
        order_value_median=1_850,
        staff_per_department=5,
        gap_overrides={
            "Order Approved": 0.08,
            "Picking Started": 3.0,
            "Packed": 0.6,
            "Shipped": 4.0,
            "Invoice Created": 0.2,
            "Payment Received": 30.0,
        },
    ),
}


@dataclass(frozen=True)
class DemoDataset:
    name: str
    profile: str
    cases: int
    company: str
    summary: str


DEMO_DATASETS = (
    DemoDataset(
        "Manufacturing", "manufacturing", 10_000, "Synthetic Manufacturing Company",
        "Make-to-order production with material shortages and quality-check loops.",
    ),
    DemoDataset(
        "Retail", "retail", 5_000, "Synthetic Online Retailer",
        "Fast fulfilment, short payment terms, cancellations and returns after payment.",
    ),
    DemoDataset(
        "Clean Process", "clean", 5_000, "Synthetic Distributor (baseline)",
        "The standard Order-to-Cash path with no deviations: a reference point.",
    ),
    DemoDataset(
        "Messy Process", "messy", 10_000, "Synthetic Wholesale Distributor",
        "Approval rework, skipped packing, late invoices and unpaid orders.",
    ),
    DemoDataset(
        "Warehouse Delay", "warehouse", 10_000, "Synthetic Distributor (warehouse backlog)",
        "Three in ten approved orders wait one to two days before picking starts.",
    ),
)


def _activities(profile: str, spec: Profile, rng: np.random.Generator) -> list[str]:
    activities = list(spec.activities)
    if profile in {"messy", "warehouse"}:
        if rng.random() < 0.17:
            activities[2:2] = ["Order Edited", "Order Approved"]
        if rng.random() < 0.035:
            activities.remove("Packed")
        if rng.random() < 0.08:
            activities.remove("Payment Received")
    elif profile == "manufacturing":
        if rng.random() < 0.09:
            activities[2:2] = ["Order Edited", "Order Approved"]
        failures = 0
        while failures < 2 and rng.random() < (0.13 if failures == 0 else 0.25):
            failures += 1
        check = activities.index("Quality Check")
        activities[check + 1:check + 1] = ["Production Started", "Quality Check"] * failures
        if rng.random() < 0.06:
            activities.remove("Payment Received")
    elif profile == "retail":
        if rng.random() < 0.05:
            return activities[:2] + ["Order Cancelled"]
        if rng.random() < 0.04:
            # Customer corrects the delivery address after the auto-approval.
            activities[2:2] = ["Order Edited", "Order Approved"]
        if rng.random() < 0.03:
            activities.remove("Payment Received")
        elif rng.random() < 0.07:
            activities.append("Return Requested")
    return activities


def generate_events(cases: int = 10_000, seed: int = 42, profile: str = "messy") -> pd.DataFrame:
    """Generate one-order cases; variation is deliberate and independently sampled."""

    if cases < 1:
        raise ValueError("cases must be positive")
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of: {', '.join(PROFILES)}")
    spec = PROFILES[profile]
    gaps = BASE_GAP_HOURS | spec.gap_overrides
    rng = np.random.default_rng(seed)
    records: list[dict] = []
    start = pd.Timestamp("2026-01-05T08:00:00Z")

    for number in range(1, cases + 1):
        case_id = f"ORD-{number:06d}"
        order_value = round(float(rng.lognormal(np.log(spec.order_value_median), 0.58)), -1)
        timestamp = start + timedelta(minutes=int(rng.integers(0, 60 * 24 * 90)))
        activities = _activities(profile, spec, rng)

        warehouse_delay = rng.random() < {"warehouse": 0.30, "messy": 0.10}.get(profile, 0.0)
        material_shortage = profile == "manufacturing" and rng.random() < 0.15
        invoice_delay = profile not in {"clean", "retail"} and rng.random() < 0.045
        extreme_outlier = profile != "clean" and rng.random() < 0.008

        for event_order, activity in enumerate(activities, start=1):
            if event_order > 1:
                gap = float(rng.lognormal(np.log(gaps[activity]), spec.spread))
                if activity == "Picking Started" and warehouse_delay:
                    gap += float(rng.uniform(18, 55))
                if activity == "Production Started" and material_shortage:
                    gap += float(rng.uniform(48, 160))
                if activity == "Invoice Created" and invoice_delay:
                    gap += float(rng.uniform(12, 48))
                if activity == "Payment Received" and extreme_outlier:
                    gap += float(rng.uniform(24 * 25, 24 * 60))
                timestamp += timedelta(hours=gap)
            department = DEPARTMENTS[activity]
            resource = (
                "system"
                if activity == "Payment Received"
                else f"{department.lower().replace(' ', '_')}_{int(rng.integers(1, spec.staff_per_department + 1)):02d}"
            )
            records.append(
                {
                    "case_id": case_id,
                    "activity": activity,
                    "timestamp": timestamp.isoformat(timespec="seconds"),
                    "resource": resource,
                    "department": department,
                    "cost": round(float(rng.uniform(1.0, 18.0)), 2) if activity != "Payment Received" else 0.0,
                    "order_value": order_value,
                    "event_order": event_order,
                }
            )

    return pd.DataFrame.from_records(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ERP event logs")
    parser.add_argument("--cases", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="messy")
    parser.add_argument("--output", type=Path, default=Path("data/demo_messy.csv"))
    arguments = parser.parse_args()
    output = arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = generate_events(arguments.cases, arguments.seed, arguments.profile)
    frame.to_csv(output, index=False)
    print(f"Generated {len(frame):,} events for {arguments.cases:,} cases at {output}")


if __name__ == "__main__":
    main()
