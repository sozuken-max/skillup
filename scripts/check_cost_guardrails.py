"""Fail when infrastructure or deploy config would cost money with zero traffic.

The project must run at $0 at idle (ADR-0007). This is a deliberately simple text check of
infra/*.tf and the deploy workflow; anything it flags needs an ADR, not a workaround.

Usage:
    python -m scripts.check_cost_guardrails
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INFRA = ROOT / "infra"
DEPLOY = ROOT / ".github" / "workflows" / "deploy.yml"
MAX_INSTANCES = 3

# Resources that bill per hour whether or not anyone uses them.
ALWAYS_ON = {
    "google_sql_database_instance": "Cloud SQL (use Neon, ADR-0003)",
    "google_alloydb_cluster": "AlloyDB",
    "google_redis_instance": "Memorystore",
    "google_compute_instance": "Compute Engine VM",
    "google_container_cluster": "GKE",
    "google_vpc_access_connector": "Serverless VPC connector",
    "google_compute_router_nat": "Cloud NAT",
    "google_compute_global_forwarding_rule": "Load balancer",
    "google_compute_forwarding_rule": "Load balancer",
    "google_cloud_run_v2_worker_pool": "Cloud Run worker pool",
}
TF_MIN_RE = re.compile(r"\bmin_instance_count\s*=\s*(\d+)")
FLAG_MIN_RE = re.compile(r"--min-instances[= ](\d+)")
FLAG_MAX_RE = re.compile(r"--max-instances[= ](\d+)")


def check_terraform(infra: Path) -> list[str]:
    errors: list[str] = []
    text = "\n".join(p.read_text(encoding="utf-8") for p in sorted(infra.glob("*.tf")))
    for resource, label in ALWAYS_ON.items():
        if re.search(rf'resource\s+"{resource}"', text):
            errors.append(f"infra: {resource} ({label}) costs money at idle")
    for value in TF_MIN_RE.findall(text):
        if int(value) > 0:
            errors.append(f"infra: min_instance_count = {value}; must be 0")
    if re.search(r'resource\s+"google_artifact_registry_repository"', text) and (
        "cleanup_policies" not in text
    ):
        errors.append("infra: Artifact Registry repository needs cleanup_policies (0.5 GB free)")
    if "google_billing_budget" not in text:
        errors.append("infra: a google_billing_budget alert is required")
    return errors


def check_deploy(deploy: Path) -> list[str]:
    if not deploy.exists():
        return []
    text = deploy.read_text(encoding="utf-8")
    errors: list[str] = []
    mins = FLAG_MIN_RE.findall(text)
    if not mins:
        errors.append("deploy.yml: every Cloud Run deploy must pass --min-instances=0")
    errors += [f"deploy.yml: --min-instances={m}; must be 0" for m in mins if int(m) != 0]
    maxes = FLAG_MAX_RE.findall(text)
    if not maxes:
        errors.append("deploy.yml: every Cloud Run deploy must set --max-instances")
    errors += [
        f"deploy.yml: --max-instances={m} is above {MAX_INSTANCES}"
        for m in maxes
        if int(m) > MAX_INSTANCES
    ]
    if "--no-cpu-throttling" in text:
        errors.append("deploy.yml: --no-cpu-throttling switches to instance billing")
    return errors


def main() -> int:
    errors = check_terraform(INFRA) + check_deploy(DEPLOY)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    print(f"cost guardrails: {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
