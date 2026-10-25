"""Check that requirements, tests and evals stay linked.

Every acceptance criterion (AC) of an approved requirement must be covered by at least one
passing test (``@pytest.mark.req("REQ-NNN.AC-n")``) or one eval case (``"req": "REQ-NNN.AC-n"``).
See docs/requirements/README.md for the full rules.

Usage:
    python -m scripts.check_traceability \
        [--results reports/req-results.json] [--base origin/main] \
        [--pr-title "..."] [--branch "..."]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
REQ_DIR = ROOT / "docs" / "requirements"
TEST_DIR = ROOT / "tests"
EVAL_DIR = ROOT / "evals" / "datasets"
REPORT = ROOT / "reports" / "traceability.md"

STATUSES = {"draft", "approved", "deprecated"}
REQ_FILE_RE = re.compile(r"^(REQ-\d{3})-[a-z0-9-]+\.md$")
AC_LINE_RE = re.compile(r"^- \*\*(AC-\d+)\*\*(?:\s*\(eval\))?:\s*(.+)$")
TEST_REF_RE = re.compile(r"""mark\.req\(([^)]*)\)""")
REF_RE = re.compile(r"REQ-\d{3}\.AC-\d+")
REQ_ID_RE = re.compile(r"REQ-\d{3}", re.IGNORECASE)
# Paths whose changes must name a requirement, and PR title prefixes that are exempt.
TRACED_PATHS = ("app/", "migrations/")
EXEMPT_PREFIXES = ("chore", "fix", "deps", "docs", "ci", "build")


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


@dataclass
class Requirement:
    id: str
    status: str
    path: Path
    criteria: dict[str, str] = field(default_factory=dict[str, str])


def parse_requirement(path: Path, errors: list[str]) -> Requirement | None:
    match = REQ_FILE_RE.match(path.name)
    if not match:
        errors.append(f"{path.name}: file name must look like REQ-NNN-short-slug.md")
        return None
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if not text.startswith("---") or len(parts) < 3:
        errors.append(f"{path.name}: missing YAML front matter")
        return None
    loaded: object = yaml.safe_load(parts[1])
    meta = cast(dict[str, object], loaded) if isinstance(loaded, dict) else {}
    req = Requirement(id=str(meta.get("id", "")), status=str(meta.get("status", "")), path=path)
    if req.id != match.group(1):
        errors.append(f"{path.name}: front matter id '{req.id}' does not match the file name")
    if req.status not in STATUSES:
        errors.append(f"{path.name}: status must be one of {sorted(STATUSES)}")
    for line in parts[2].splitlines():
        ac = AC_LINE_RE.match(line.strip())
        if not ac:
            continue
        if ac.group(1) in req.criteria:
            errors.append(f"{path.name}: duplicate {ac.group(1)}")
        req.criteria[ac.group(1)] = ac.group(2).strip()
    if req.status == "approved" and not req.criteria:
        errors.append(f"{path.name}: approved requirement has no acceptance criteria")
    return req


def load_requirements(req_dir: Path, errors: list[str]) -> dict[str, Requirement]:
    reqs: dict[str, Requirement] = {}
    for path in sorted(req_dir.glob("REQ-*.md")):
        req = parse_requirement(path, errors)
        if req is None:
            continue
        if req.id in reqs:
            errors.append(f"{path.name}: {req.id} is already used by {reqs[req.id].path.name}")
        reqs[req.id] = req
    return reqs


def find_test_refs(test_dir: Path) -> dict[str, set[str]]:
    """Map each AC reference found in test files to the files that contain it.

    tests/tooling/ tests this script itself, so its sample references are skipped.
    """
    refs: dict[str, set[str]] = {}
    for path in test_dir.rglob("*.py"):
        if "tooling" in path.relative_to(test_dir).parts:
            continue
        for call in TEST_REF_RE.findall(path.read_text(encoding="utf-8")):
            for ref in REF_RE.findall(call):
                refs.setdefault(ref, set()).add(_rel(path))
    return refs


def find_eval_refs(eval_dir: Path, errors: list[str]) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for path in eval_dir.rglob("*.jsonl"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                ref = json.loads(line).get("req")
            except json.JSONDecodeError:
                errors.append(f"{path.name}:{n}: invalid JSON")
                continue
            if ref:
                refs.setdefault(str(ref), set()).add(f"{_rel(path)}:{n}")
    return refs


def load_results(path: Path | None) -> dict[str, list[tuple[str, str]]]:
    """Read pytest outcomes per AC, as written by tests/conftest.py."""
    if path is None or not path.exists():
        return {}
    data: dict[str, list[list[str]]] = json.loads(path.read_text(encoding="utf-8"))
    return {ref: [(test, outcome) for test, outcome in runs] for ref, runs in data.items()}


def changed_files(base: str) -> list[str]:
    out = subprocess.run(  # noqa: S603
        ["git", "diff", "--name-only", f"{base}...HEAD"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def base_criteria(base: str, path: Path) -> dict[str, str] | None:
    """Return the ACs of a requirement file as it was on the base ref, or None if it is new."""
    rel = _rel(path)
    out = subprocess.run(  # noqa: S603
        ["git", "show", f"{base}:{rel}"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return None
    criteria: dict[str, str] = {}
    for line in out.stdout.splitlines():
        ac = AC_LINE_RE.match(line.strip())
        if ac:
            criteria[ac.group(1)] = ac.group(2).strip()
    return criteria


def check(
    reqs: dict[str, Requirement],
    test_refs: dict[str, set[str]],
    eval_refs: dict[str, set[str]],
    results: dict[str, list[tuple[str, str]]],
    use_results: bool,
) -> tuple[list[str], list[str]]:
    """Return (errors, matrix rows)."""
    errors: list[str] = []
    rows: list[str] = []
    known = {f"{r.id}.{ac}": r for r in reqs.values() for ac in r.criteria}

    for ref in sorted(set(test_refs) | set(eval_refs)):
        where = ", ".join(sorted(test_refs.get(ref, set()) | eval_refs.get(ref, set())))
        if ref not in known:
            errors.append(f"{ref} is referenced in {where} but no such criterion exists")
        elif known[ref].status == "deprecated":
            errors.append(f"{ref} belongs to a deprecated requirement; remove it from {where}")

    for req in sorted(reqs.values(), key=lambda r: r.id):
        if req.status != "approved":
            continue
        for ac in req.criteria:
            ref = f"{req.id}.{ac}"
            runs = results.get(ref, [])
            evals = eval_refs.get(ref, set())
            if use_results:
                passed = [t for t, outcome in runs if outcome == "passed"]
                failed = [t for t, outcome in runs if outcome != "passed"]
            else:
                passed, failed = sorted(test_refs.get(ref, set())), []
            if failed:
                errors.append(f"{ref}: tests not passing: {', '.join(failed)}")
            if not passed and not evals:
                errors.append(f"{ref}: no passing test or eval case covers this criterion")
            covered = (
                ", ".join(
                    passed
                    + [f"{t} ({o})" for t, o in runs if o != "passed"]
                    + sorted(f"eval {e}" for e in evals)
                )
                or "-"
            )
            mark = "FAIL" if failed or not (passed or evals) else "ok"
            rows.append(f"| {ref} | {covered} | {mark} |")
    return errors, rows


def check_pr(title: str, branch: str, files: list[str]) -> list[str]:
    if not any(f.startswith(TRACED_PATHS) for f in files):
        return []
    if REQ_ID_RE.search(title) or REQ_ID_RE.search(branch):
        return []
    if title.lower().startswith(EXEMPT_PREFIXES):
        return []
    return [
        "This PR changes app/ or migrations/ but its title and branch name no requirement. "
        f"Add a REQ-NNN ID, or prefix the title with one of {', '.join(EXEMPT_PREFIXES)}."
    ]


def check_changed_criteria(
    reqs: dict[str, Requirement], test_refs: dict[str, set[str]], base: str, files: list[str]
) -> list[str]:
    """A changed criterion must come with a change to at least one test that covers it."""
    errors: list[str] = []
    changed = set(files)
    for req in reqs.values():
        if _rel(req.path) not in changed or req.status != "approved":
            continue
        before = base_criteria(base, req.path)
        if before is None:
            continue
        for ac, text in req.criteria.items():
            if ac in before and before[ac] != text:
                ref = f"{req.id}.{ac}"
                tests = test_refs.get(ref, set())
                if tests and not tests & changed:
                    errors.append(
                        f"{ref} changed, but none of its tests did: {', '.join(sorted(tests))}"
                    )
    return errors


def write_report(rows: list[str], errors: list[str]) -> None:
    lines = ["## Traceability", "", "| Criterion | Covered by | Result |", "|---|---|---|"]
    lines += rows or ["| (no approved requirements yet) | | |"]
    if errors:
        lines += ["", "### Errors", *[f"- {e}" for e in errors]]
    report = "\n".join(lines) + "\n"
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check requirement traceability.")
    parser.add_argument("--results", type=Path, help="pytest per-criterion results JSON")
    parser.add_argument("--base", help="git ref to diff against, e.g. origin/main")
    parser.add_argument("--pr-title", default="")
    parser.add_argument("--branch", default="")
    args = parser.parse_args(argv)

    errors: list[str] = []
    reqs = load_requirements(REQ_DIR, errors)
    test_refs = find_test_refs(TEST_DIR)
    eval_refs = find_eval_refs(EVAL_DIR, errors)
    results = load_results(args.results)
    found, rows = check(reqs, test_refs, eval_refs, results, use_results=args.results is not None)
    errors += found
    if args.base:
        files = changed_files(args.base)
        errors += check_pr(args.pr_title, args.branch, files)
        errors += check_changed_criteria(reqs, test_refs, args.base, files)

    write_report(rows, errors)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    print(f"{len(reqs)} requirements, {len(rows)} approved criteria, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
