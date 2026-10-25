"""PostToolUse hook: format and lint a Python file right after Claude edits it.

Lint problems that ruff can't fix are reported back to Claude (exit code 2) so it fixes them
in the same turn instead of finding out in CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    event = json.load(sys.stdin)
    path = Path(str(event.get("tool_input", {}).get("file_path", "")))
    if path.suffix != ".py" or "bq-model" in path.parts or not path.exists():
        return 0
    ruff = ["uv", "run", "--quiet", "ruff"]
    subprocess.run([*ruff, "format", "--quiet", str(path)], check=False)  # noqa: S603
    lint = subprocess.run(  # noqa: S603
        [*ruff, "check", "--fix", "--quiet", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if lint.returncode != 0:
        print(f"ruff found problems in {path.name}:\n{lint.stdout}{lint.stderr}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
