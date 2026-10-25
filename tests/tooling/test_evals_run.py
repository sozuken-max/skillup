from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evals import run


@pytest.fixture
def evals_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "suites").mkdir()
    (tmp_path / "datasets").mkdir()
    (tmp_path / "suites" / "demo.py").write_text("def score(case):\n    return 1.0\n")
    (tmp_path / "datasets" / "demo.jsonl").write_text('{"id": "a"}\n\n{"id": "b"}\n')
    monkeypatch.setattr(run, "SUITES", tmp_path / "suites")
    monkeypatch.setattr(run, "DATASETS", tmp_path / "datasets")
    monkeypatch.setattr(run, "PROMPTS", tmp_path / "prompts")
    return tmp_path


def test_scores_are_cached_until_the_suite_changes(evals_dir: Path) -> None:
    calls: list[str] = []

    def scorer(case: dict[str, Any]) -> float:
        calls.append(case["id"])
        return 0.5

    cache: dict[str, float] = {}
    cases = run.load_cases("demo")
    assert run.run_suite("demo", scorer, cases, cache) == 0.5
    assert run.run_suite("demo", scorer, cases, cache) == 0.5
    assert calls == ["a", "b"]

    (evals_dir / "suites" / "demo.py").write_text("def score(case):\n    return 0.0\n")
    run.run_suite("demo", scorer, cases, cache)
    assert calls == ["a", "b", "a", "b"]


def test_prompt_changes_invalidate_the_cache(evals_dir: Path) -> None:
    before = run.fingerprint("demo")
    (evals_dir / "prompts").mkdir()
    (evals_dir / "prompts" / "gap.txt").write_text("Explain the gap.")
    assert run.fingerprint("demo") != before


def test_no_suites_is_not_an_error(evals_dir: Path) -> None:
    (evals_dir / "suites" / "demo.py").unlink()
    assert run.main([]) == 0
