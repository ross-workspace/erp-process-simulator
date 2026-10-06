"""Headless smoke tests for the Streamlit app (no browser needed)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["overview", "process_map", "bottlenecks", "variants", "cases", "simulation", "data_import"]


def _app() -> AppTest:
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_errors(page: str) -> None:
    app = _app()
    app.session_state["dataset"] = "Retail"  # smallest demo keeps the suite quick
    app.run()
    if page != "overview":
        app.switch_page(f"app_pages/{page}.py").run()
    assert not app.exception, [item.message for item in app.exception]
    assert not app.error, [item.value for item in app.error]


def test_uploaded_log_becomes_the_active_dataset() -> None:
    from dashboard.state import UPLOAD_PREFIX

    payload = (ROOT / "data" / "sample_event_log.csv").read_bytes()
    app = _app()
    label = f"{UPLOAD_PREFIX}sample.csv"
    app.session_state["uploads"] = {label: ("sample", payload)}
    app.session_state["dataset"] = label
    app.run()
    assert not app.exception
    assert any("250" in str(item.value) for item in app.markdown)
