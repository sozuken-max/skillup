from __future__ import annotations

import subprocess
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


def test_more_malformed_cases(tmp_path: Path) -> None:
    (tmp_path / "REQ-003-nofm.md").write_text("no front matter\n")
    (tmp_path / "REQ-004-empty.md").write_text("---\nid: REQ-004\nstatus: approved\n---\nnone\n")
    (tmp_path / "REQ-005-dup.md").write_text(
        "---\nid: REQ-005\nstatus: draft\n---\n- **AC-1**: a\n- **AC-1**: b\n"
    )
    (tmp_path / "REQ-005-again.md").write_text("---\nid: REQ-005\nstatus: draft\n---\n")
    _, errors = load(tmp_path)
    assert any("missing YAML front matter" in e for e in errors)
    assert any("has no acceptance criteria" in e for e in errors)
    assert any("duplicate AC-1" in e for e in errors)
    assert any("REQ-005 is already used" in e for e in errors)


def test_load_results(tmp_path: Path) -> None:
    assert ct.load_results(None) == {}
    assert ct.load_results(tmp_path / "missing.json") == {}
    path = tmp_path / "r.json"
    path.write_text('{"REQ-001.AC-1": [["t::a", "passed"]]}')
    assert ct.load_results(path) == {"REQ-001.AC-1": [("t::a", "passed")]}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway git repo laid out like this one, with ct pointed at it."""
    for sub in ("docs/requirements", "tests", "evals/datasets"):
        (tmp_path / sub).mkdir(parents=True)
    monkeypatch.setattr(ct, "ROOT", tmp_path)
    monkeypatch.setattr(ct, "REQ_DIR", tmp_path / "docs/requirements")
    monkeypatch.setattr(ct, "TEST_DIR", tmp_path / "tests")
    monkeypatch.setattr(ct, "EVAL_DIR", tmp_path / "evals/datasets")
    monkeypatch.setattr(ct, "REPORT", tmp_path / "reports/traceability.md")
    git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


def git(cwd: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],  # noqa: S607
        cwd=cwd,
        check=True,
    )


def test_main_end_to_end(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_req(repo / "docs/requirements")
    marker = "@pytest.mark." + "req"
    (repo / "tests/test_a.py").write_text(f'{marker}("REQ-001.AC-1")\n')
    (repo / "evals/datasets/s.jsonl").write_text('{"req": "REQ-001.AC-2"}\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    summary = repo / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert ct.main([]) == 0
    assert "| REQ-001.AC-1 | tests/test_a.py | ok |" in summary.read_text()

    # Change AC-1's wording without touching its test.
    req = repo / "docs/requirements/REQ-001-example.md"
    req.write_text(req.read_text().replace("Returns 200.", "Returns 201."))
    git(repo, "commit", "-qam", "change")
    assert ct.main(["--base", "HEAD~1", "--pr-title", "REQ-001: change"]) == 1
    assert "REQ-001.AC-1 changed, but none of its tests did" in ct.REPORT.read_text()

    # Updating the test in the same change satisfies the rule.
    (repo / "tests/test_a.py").write_text(f'{marker}("REQ-001.AC-1")\n# 201\n')
    git(repo, "commit", "-qam", "test")
    assert ct.main(["--base", "HEAD~2", "--pr-title", "REQ-001: change"]) == 0


def test_new_requirement_has_no_base(repo: Path) -> None:
    git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    path = write_req(repo / "docs/requirements")
    assert ct.base_criteria("HEAD", path) is None
