from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_traceability as ct

REQ = """---
id: REQ-001
title: Example
status: {status}
owner: "@me"
issue: 1
---
## Acceptance criteria
- **AC-1**: Returns 200.
- **AC-2** (eval): Explanation scores at least 0.8.
"""


def write_req(directory: Path, status: str = "approved", name: str = "REQ-001-example.md") -> Path:
    path = directory / name
    path.write_text(REQ.format(status=status), encoding="utf-8")
    return path


def load(directory: Path) -> tuple[dict[str, ct.Requirement], list[str]]:
    errors: list[str] = []
    return ct.load_requirements(directory, errors), errors


def test_parses_front_matter_and_criteria(tmp_path: Path) -> None:
    write_req(tmp_path)
    reqs, errors = load(tmp_path)
    assert errors == []
    assert reqs["REQ-001"].status == "approved"
    assert reqs["REQ-001"].criteria == {
        "AC-1": "Returns 200.",
        "AC-2": "Explanation scores at least 0.8.",
    }


@pytest.mark.parametrize(
    ("name", "status", "message"),
    [
        ("REQ-1-bad.md", "approved", "file name"),
        ("REQ-002-mismatch.md", "approved", "does not match"),
        ("REQ-001-example.md", "done", "status must be"),
    ],
)
def test_rejects_malformed_requirements(
    tmp_path: Path, name: str, status: str, message: str
) -> None:
    write_req(tmp_path, status=status, name=name)
    _, errors = load(tmp_path)
    assert any(message in e for e in errors)


def test_approved_criteria_need_coverage(tmp_path: Path) -> None:
    write_req(tmp_path)
    reqs, _ = load(tmp_path)
    errors, rows = ct.check(reqs, {}, {}, {}, use_results=True)
    assert len(errors) == 2
    assert all("no passing test or eval case" in e for e in errors)
    assert all(row.endswith("FAIL |") for row in rows)


def test_passing_test_and_eval_case_cover_criteria(tmp_path: Path) -> None:
    write_req(tmp_path)
    reqs, _ = load(tmp_path)
    results = {"REQ-001.AC-1": [("tests/test_x.py::test_ok", "passed")]}
    evals = {"REQ-001.AC-2": {"evals/datasets/s.jsonl:1"}}
    errors, rows = ct.check(reqs, {"REQ-001.AC-1": {"tests/test_x.py"}}, evals, results, True)
    assert errors == []
    assert all(row.endswith("ok |") for row in rows)


def test_failing_test_is_reported(tmp_path: Path) -> None:
    write_req(tmp_path)
    reqs, _ = load(tmp_path)
    results = {"REQ-001.AC-1": [("tests/test_x.py::test_bad", "failed")]}
    evals = {"REQ-001.AC-2": {"evals/datasets/s.jsonl:1"}}
    errors, _ = ct.check(reqs, {}, evals, results, use_results=True)
    assert errors == [
        "REQ-001.AC-1: tests not passing: tests/test_x.py::test_bad",
        "REQ-001.AC-1: no passing test or eval case covers this criterion",
    ]


def test_draft_requirements_need_no_coverage(tmp_path: Path) -> None:
    write_req(tmp_path, status="draft")
    reqs, _ = load(tmp_path)
    assert ct.check(reqs, {}, {}, {}, use_results=True) == ([], [])


def test_unknown_and_deprecated_references_fail(tmp_path: Path) -> None:
    write_req(tmp_path, status="deprecated")
    reqs, _ = load(tmp_path)
    refs = {"REQ-001.AC-1": {"tests/a.py"}, "REQ-009.AC-1": {"tests/b.py"}}
    errors, _ = ct.check(reqs, refs, {}, {}, use_results=False)
    assert any("REQ-001.AC-1 belongs to a deprecated" in e for e in errors)
    assert any("REQ-009.AC-1 is referenced in tests/b.py but no such" in e for e in errors)


def test_finds_references_in_tests_and_evals(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    marker = "@pytest.mark." + "req"
    (tests / "test_a.py").write_text(f'{marker}("REQ-001.AC-1", "REQ-001.AC-2")\n')
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    (datasets / "s.jsonl").write_text('{"id": "a", "req": "REQ-001.AC-2"}\n\nnot json\n')
    assert set(ct.find_test_refs(tests)) == {"REQ-001.AC-1", "REQ-001.AC-2"}
    errors: list[str] = []
    assert set(ct.find_eval_refs(datasets, errors)) == {"REQ-001.AC-2"}
    assert errors == ["s.jsonl:3: invalid JSON"]


@pytest.mark.parametrize(
    ("title", "branch", "files", "ok"),
    [
        ("Add report", "feature", ["docs/x.md"], True),
        ("Add report", "feature", ["app/main.py"], False),
        ("REQ-007: add report", "feature", ["app/main.py"], True),
        ("Add report", "req-007/report", ["app/main.py"], True),
        ("fix: typo in error", "hotfix", ["app/main.py"], True),
    ],
)
def test_pr_must_name_requirement_when_app_changes(
    title: str, branch: str, files: list[str], ok: bool
) -> None:
    assert (ct.check_pr(title, branch, files) == []) is ok
