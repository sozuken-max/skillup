"""Shared pytest setup.

Registers the ``req`` marker and writes reports/req-results.json, which maps each
acceptance criterion to the outcome of the tests that cover it. scripts/check_traceability.py
reads that file in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULTS = Path(__file__).resolve().parent.parent / "reports" / "req-results.json"
_outcomes: dict[str, str] = {}
_refs: dict[str, list[str]] = {}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", 'req(*ids): acceptance criteria this test proves, e.g. req("REQ-007.AC-3")'
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        ids = [str(i) for marker in item.iter_markers("req") for i in marker.args]
        if ids:
            _refs[item.nodeid] = ids


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.nodeid not in _refs:
        return
    # A failure or skip in any phase wins over a pass in another.
    already_failed = _outcomes.get(report.nodeid, "passed") != "passed"
    if (report.when == "call" or report.outcome != "passed") and not already_failed:
        _outcomes[report.nodeid] = report.outcome


def pytest_sessionfinish(session: pytest.Session) -> None:
    if not _refs:
        return
    results: dict[str, list[tuple[str, str]]] = {}
    for nodeid, ids in _refs.items():
        for ref in ids:
            results.setdefault(ref, []).append((nodeid, _outcomes.get(nodeid, "not run")))
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
