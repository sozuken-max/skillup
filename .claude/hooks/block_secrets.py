"""PreToolUse hook: refuse to write content that looks like a credential.

Exit code 2 blocks the edit and shows the reason to Claude.
"""

from __future__ import annotations

import json
import re
import sys

PATTERNS = {
    "OpenAI API key": r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}",
    "Anthropic API key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "Google API key": r"AIza[0-9A-Za-z_-]{35}",
    "GCP service account key": r'"type"\s*:\s*"service_account"',
    "private key": r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
    "GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "Postgres URL with password": (
        r"postgres(?:ql)?://[^:\s/]+:(?![<$])[^@\s]+@(?!localhost|127\.0\.0\.1|db[:/])"
    ),
}


def main() -> int:
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input", {})
    text = "\n".join(
        str(tool_input.get(key, "")) for key in ("content", "new_string", "new_source")
    )
    found = [name for name, pattern in PATTERNS.items() if re.search(pattern, text)]
    if not found:
        return 0
    print(
        f"Blocked: this edit seems to contain a secret ({', '.join(found)}). "
        "Secrets go in Secret Manager or a local .env (gitignored), never in the repo. "
        "Use a placeholder such as ${OPENAI_API_KEY} instead.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
