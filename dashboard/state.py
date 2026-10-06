"""Session state, data sources and cached analysis shared by every page."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO, StringIO

import pandas as pd
import streamlit as st

from erp_process_analyzer import Analysis, DataValidationError, ImportReport, analyze, load_events
from erp_process_analyzer.generator import DEMO_DATASETS, DemoDataset, generate_events

DEMOS: dict[str, DemoDataset] = {demo.name: demo for demo in DEMO_DATASETS}
DEFAULT_DATASET = "Messy Process"
UPLOAD_PREFIX = "Upload · "
SEED = 42
TIMEZONES = ["UTC", "Europe/Prague", "Europe/Berlin", "Europe/London", "America/New_York", "Asia/Singapore"]
CURRENCIES = {"CZK": "{value} Kč", "EUR": "€{value}", "USD": "${value}", "GBP": "£{value}"}


@dataclass(frozen=True)
class Source:
    """The dataset currently on screen."""

    label: str
    company: str
    summary: str
    events: pd.DataFrame
    report: ImportReport
    analysis: Analysis
    is_demo: bool


def init_state() -> None:
    defaults = {
        "dataset": DEFAULT_DATASET,
        "uploads": {},
        "upload_error": None,
        "timezone": "UTC",
        "currency": "CZK",
        "map_mode": "Frequency",
        "map_zoom": 100,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


# Results are treated as read-only by the pages, so cache_resource avoids
# copying ~100k-row frames on every rerun.
@st.cache_resource(show_spinner="Generating demo event log…", max_entries=6)
def _demo(name: str) -> tuple[pd.DataFrame, ImportReport, Analysis]:
    demo = DEMOS[name]
    frame = generate_events(demo.cases, SEED, demo.profile)
    events, report = load_events(StringIO(frame.to_csv(index=False)))
    return events, report, analyze(events)


@st.cache_resource(show_spinner="Analyzing uploaded log…", max_entries=4)
def _upload(digest: str, timezone: str, _payload: bytes) -> tuple[pd.DataFrame, ImportReport, Analysis]:
    events, report = load_events(BytesIO(_payload), timezone_for_naive=timezone)
    return events, report, analyze(events)


def dataset_options() -> list[str]:
    return list(DEMOS) + list(st.session_state.uploads)


def demo_label(name: str) -> str:
    demo = DEMOS.get(name)
    return f"{name} ({demo.cases // 1000}k)" if demo else name


def select_dataset(widget_key: str) -> None:
    value = st.session_state.get(widget_key)
    if value:
        st.session_state.dataset = value


def handle_upload(widget_key: str) -> None:
    file = st.session_state.get(widget_key)
    if file is None:
        return
    payload = file.getvalue()
    digest = hashlib.sha256(payload).hexdigest()[:16]
    try:
        _upload(digest, st.session_state.timezone, payload)
    except DataValidationError as exc:
        st.session_state.upload_error = (file.name, list(exc.problems))
        return
    label = f"{UPLOAD_PREFIX}{file.name}"
    st.session_state.uploads[label] = (digest, payload)
    st.session_state.upload_error = None
    st.session_state.dataset = label


def current_source() -> Source:
    label = st.session_state.dataset
    if label in st.session_state.uploads:
        digest, payload = st.session_state.uploads[label]
        try:
            events, report, analysis = _upload(digest, st.session_state.timezone, payload)
        except DataValidationError as exc:
            st.error(f"This file no longer imports with timezone {st.session_state.timezone}:\n\n{exc}")
            st.stop()
        return Source(label, label.removeprefix(UPLOAD_PREFIX), "Your uploaded event log.", events, report, analysis, False)
    if label not in DEMOS:
        label = st.session_state.dataset = DEFAULT_DATASET
    demo = DEMOS[label]
    events, report, analysis = _demo(label)
    return Source(label, demo.company, demo.summary, events, report, analysis, True)


def money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    template = CURRENCIES.get(st.session_state.get("currency", "CZK"), "{value}")
    return template.format(value=f"{value:,.0f}")


def _copy(widget_key: str, store_key: str) -> None:
    st.session_state[store_key] = st.session_state[widget_key]


def bind(store_key: str) -> dict:
    """Widget kwargs that keep a value alive on pages where the widget is absent.

    Streamlit drops widget-keyed state when the widget is not rendered, so the
    durable value lives under ``store_key`` and the widget mirrors it.
    """

    widget_key = f"_w_{store_key}"
    st.session_state[widget_key] = st.session_state[store_key]
    return {"key": widget_key, "on_change": _copy, "args": (widget_key, store_key)}
