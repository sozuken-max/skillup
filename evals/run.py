"""Run eval suites against their golden datasets and fail on score regressions.

A suite is a module in evals/suites/ that defines ``score(case: dict) -> float`` returning 0..1.
Its cases live in evals/datasets/<suite>.jsonl, one JSON object per line:
    {"id": "cv-basic-01", "req": "REQ-007.AC-4", "input": {...}, "expected": {...}}
Minimum mean scores live in evals/thresholds.yaml. Scores are cached by a hash of the suite's
source, its prompts and the case, so unchanged suites cost nothing to re-run.

Usage:
    python -m evals.run [suite ...]
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parent
DATASETS = ROOT / "datasets"
SUITES = ROOT / "suites"
PROMPTS = ROOT.parent / "app" / "prompts"
CACHE = ROOT / ".cache" / "scores.json"
THRESHOLDS = ROOT / "thresholds.yaml"

Scorer = Callable[[dict[str, Any]], float]


def load_cases(suite: str) -> list[dict[str, Any]]:
    path = DATASETS / f"{suite}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [cast(dict[str, Any], json.loads(line)) for line in lines if line.strip()]


def fingerprint(suite: str) -> str:
    """Hash of everything that can change a suite's scores, other than the cases."""
    digest = hashlib.sha256((SUITES / f"{suite}.py").read_bytes())
    if PROMPTS.exists():
        for path in sorted(PROMPTS.rglob("*")):
            if path.is_file():
                digest.update(path.read_bytes())
    return digest.hexdigest()


def run_suite(
    suite: str, scorer: Scorer, cases: list[dict[str, Any]], cache: dict[str, float]
) -> float:
    base = fingerprint(suite)
    scores: list[float] = []
    for case in cases:
        key = hashlib.sha256((base + json.dumps(case, sort_keys=True)).encode()).hexdigest()
        if key not in cache:
            cache[key] = float(scorer(case))
        scores.append(cache[key])
    return sum(scores) / len(scores) if scores else 0.0


def main(argv: list[str] | None = None) -> int:
    requested = argv if argv is not None else sys.argv[1:]
    available = sorted(p.stem for p in SUITES.glob("*.py") if p.stem != "__init__")
    suites = requested or available
    if not suites:
        print("No eval suites yet. Add one with the first LLM requirement (see evals/CLAUDE.md).")
        return 0

    thresholds = cast(dict[str, float], yaml.safe_load(THRESHOLDS.read_text()) or {})
    cache: dict[str, float] = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    failed = False
    for suite in suites:
        if suite not in thresholds:
            print(f"{suite}: no threshold in thresholds.yaml", file=sys.stderr)
            failed = True
            continue
        module = importlib.import_module(f"evals.suites.{suite}")
        mean = run_suite(suite, module.score, load_cases(suite), cache)
        ok = mean >= thresholds[suite]
        failed |= not ok
        print(f"{suite}: {mean:.3f} (threshold {thresholds[suite]:.3f}) {'ok' if ok else 'FAIL'}")

    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
