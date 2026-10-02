"""CSV validation and event normalization.

Rows are never silently discarded. The source row number remains available for
case inspection and for explaining ambiguous event order.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TextIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

REQUIRED_COLUMNS = ("case_id", "activity", "timestamp")
OPTIONAL_COLUMNS = ("resource", "department", "cost", "order_value", "event_order")


@dataclass(frozen=True)
class ImportReport:
    rows: int
    cases: int
    duplicate_rows: int
    tied_timestamp_rows: int
    ambiguous_cases: int
    timezone_for_naive: str
    warnings: tuple[str, ...]


class DataValidationError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = tuple(problems)
        super().__init__("\n".join(problems))


def _parse_timestamp(value: str, timezone_for_naive: str) -> pd.Timestamp:
    parsed = pd.Timestamp(value)
    if pd.isna(parsed):
        raise ValueError("empty timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize(timezone_for_naive, ambiguous="raise", nonexistent="raise")
    return parsed.tz_convert("UTC")


def load_events(
    source: str | Path | BinaryIO | TextIO,
    *,
    timezone_for_naive: str = "UTC",
) -> tuple[pd.DataFrame, ImportReport]:
    """Load one event per CSV row, or raise with actionable source row numbers."""

    try:
        ZoneInfo(timezone_for_naive)
    except ZoneInfoNotFoundError as exc:
        raise DataValidationError([f"Unknown timezone: {timezone_for_naive}"]) from exc

    try:
        frame = pd.read_csv(source, dtype="string", keep_default_na=False)
    except (OSError, pd.errors.ParserError, UnicodeError) as exc:
        raise DataValidationError([f"Could not read CSV: {exc}"]) from exc

    frame.columns = [str(column).strip() for column in frame.columns]
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise DataValidationError([f"Missing required column(s): {', '.join(missing)}"])
    if frame.empty:
        raise DataValidationError(["The CSV contains no event rows."])

    frame = frame.copy()
    frame["source_row"] = range(2, len(frame) + 2)
    problems: list[str] = []
    for column in REQUIRED_COLUMNS:
        frame[column] = frame[column].astype("string").str.strip()
        blank_rows = frame.loc[frame[column].eq(""), "source_row"].tolist()
        if blank_rows:
            problems.append(f"Blank {column} at CSV row(s): {', '.join(map(str, blank_rows[:8]))}")

    if problems:
        raise DataValidationError(problems)

    parsed_timestamps: list[pd.Timestamp] = []
    for row in frame.itertuples(index=False):
        try:
            parsed_timestamps.append(_parse_timestamp(row.timestamp, timezone_for_naive))
        except (ValueError, TypeError, OverflowError) as exc:
            problems.append(f"Invalid timestamp at CSV row {row.source_row}: {exc}")
    if problems:
        raise DataValidationError(problems[:20])
    frame["timestamp"] = pd.to_datetime(parsed_timestamps, utc=True)

    for column in ("cost", "order_value", "event_order"):
        if column not in frame.columns:
            continue
        source_values = frame[column].astype("string").str.strip()
        converted = pd.to_numeric(source_values.replace("", pd.NA), errors="coerce")
        invalid = source_values.ne("") & converted.isna()
        if invalid.any():
            rows = frame.loc[invalid, "source_row"].tolist()
            problems.append(f"Invalid {column} at CSV row(s): {', '.join(map(str, rows[:8]))}")
        if column == "event_order" and converted.notna().any():
            non_integer = converted.notna() & converted.mod(1).ne(0)
            if non_integer.any():
                rows = frame.loc[non_integer, "source_row"].tolist()
                problems.append(f"Non-integer event_order at CSV row(s): {', '.join(map(str, rows[:8]))}")
        frame[column] = converted
    if problems:
        raise DataValidationError(problems[:20])

    for column in ("resource", "department"):
        if column in frame.columns:
            frame[column] = frame[column].astype("string").str.strip()

    # A repeated activity at the same timestamp may be genuine, so report it
    # without guessing which row to remove.
    duplicate_columns = [column for column in frame.columns if column != "source_row"]
    duplicate_rows = int(frame.duplicated(subset=duplicate_columns, keep=False).sum())
    tied = frame.duplicated(subset=["case_id", "timestamp"], keep=False)
    tied_rows = int(tied.sum())
    ambiguous = frame.loc[tied].groupby(["case_id", "timestamp"], sort=False)
    ambiguous_cases: set[str] = set()
    for (case_id, _), group in ambiguous:
        if "event_order" not in group or group["event_order"].isna().any() or group["event_order"].duplicated().any():
            ambiguous_cases.add(str(case_id))
    frame["sequence_ambiguous"] = frame["case_id"].isin(ambiguous_cases)
    order_columns = ["case_id", "timestamp"]
    if "event_order" in frame:
        order_columns.append("event_order")
    order_columns.append("source_row")
    frame = frame.sort_values(order_columns, kind="stable", na_position="last").reset_index(drop=True)

    warnings = []
    if duplicate_rows:
        warnings.append(f"{duplicate_rows:,} rows are exact duplicates; they were retained.")
    if tied_rows:
        warnings.append(f"{tied_rows:,} rows share a case and timestamp.")
    if ambiguous_cases:
        warnings.append(
            f"{len(ambiguous_cases):,} cases have ambiguous event order; CSV row order was used where needed."
        )
    report = ImportReport(
        rows=len(frame),
        cases=int(frame["case_id"].nunique()),
        duplicate_rows=duplicate_rows,
        tied_timestamp_rows=tied_rows,
        ambiguous_cases=len(ambiguous_cases),
        timezone_for_naive=timezone_for_naive,
        warnings=tuple(warnings),
    )
    return frame, report
