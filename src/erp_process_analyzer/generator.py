"""Reproducible synthetic Order-to-Cash logs for the public demo."""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

CORE_ACTIVITIES = (
    "Order Created",
    "Order Approved",
    "Picking Started",
    "Packed",
    "Shipped",
    "Invoice Created",
    "Payment Received",
)

DEPARTMENTS = {
    "Order Created": "Sales",
    "Order Approved": "Management",
    "Order Edited": "Sales",
    "Picking Started": "Warehouse",
    "Packed": "Warehouse",
    "Shipped": "Warehouse",
    "Invoice Created": "Accounting",
    "Payment Received": "Finance",
}

BASE_GAP_HOURS = {
    "Order Approved": 1.5,
    "Order Edited": 1.0,
    "Picking Started": 5.5,
    "Packed": 2.0,
    "Shipped": 1.2,
    "Invoice Created": 3.0,
    "Payment Received": 120.0,
}


def generate_events(cases: int = 10_000, seed: int = 42, profile: str = "messy") -> pd.DataFrame:
    """Generate one-order cases; variation is deliberate and independently sampled."""

    if cases < 1:
        raise ValueError("cases must be positive")
    if profile not in {"clean", "messy", "warehouse"}:
        raise ValueError("profile must be clean, messy, or warehouse")
    rng = np.random.default_rng(seed)
    records: list[dict] = []
    start = pd.Timestamp("2026-01-05T08:00:00Z")

    for number in range(1, cases + 1):
        case_id = f"ORD-{number:06d}"
        order_value = round(float(rng.lognormal(np.log(2_200), 0.58)), 2)
        timestamp = start + timedelta(minutes=int(rng.integers(0, 60 * 24 * 90)))
        activities = list(CORE_ACTIVITIES)
        if profile != "clean":
            if rng.random() < 0.17:
                activities[2:2] = ["Order Edited", "Order Approved"]
            if rng.random() < 0.035:
                activities.remove("Packed")
            if rng.random() < 0.08:
                activities.remove("Payment Received")

        warehouse_delay = profile == "warehouse" and rng.random() < 0.30
        if profile == "messy":
            warehouse_delay = rng.random() < 0.10
        invoice_delay = profile != "clean" and rng.random() < 0.045
        extreme_outlier = profile != "clean" and rng.random() < 0.008

        for event_order, activity in enumerate(activities, start=1):
            if event_order > 1:
                base = BASE_GAP_HOURS[activity]
                gap = float(rng.lognormal(np.log(base), 0.36 if profile == "clean" else 0.55))
                if activity == "Picking Started" and warehouse_delay:
                    gap += float(rng.uniform(18, 55))
                if activity == "Invoice Created" and invoice_delay:
                    gap += float(rng.uniform(12, 48))
                if activity == "Payment Received" and extreme_outlier:
                    gap += float(rng.uniform(24 * 25, 24 * 60))
                timestamp += timedelta(hours=gap)
            department = DEPARTMENTS[activity]
            resource = "system" if activity == "Payment Received" else f"{department.lower()}_{int(rng.integers(1, 9)):02d}"
            records.append(
                {
                    "case_id": case_id,
                    "activity": activity,
                    "timestamp": timestamp.isoformat(),
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
    parser.add_argument("--profile", choices=("clean", "messy", "warehouse"), default="messy")
    parser.add_argument("--output", type=Path, default=Path("data/demo_messy.csv"))
    arguments = parser.parse_args()
    output = arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = generate_events(arguments.cases, arguments.seed, arguments.profile)
    frame.to_csv(output, index=False)
    print(f"Generated {len(frame):,} events for {arguments.cases:,} cases at {output}")


if __name__ == "__main__":
    main()
