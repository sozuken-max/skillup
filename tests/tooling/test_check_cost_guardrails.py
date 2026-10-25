from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_cost_guardrails as cg

GOOD_TF = """
resource "google_artifact_registry_repository" "app" {
  cleanup_policies {}
}
resource "google_billing_budget" "monthly" {}
"""


def tf(tmp_path: Path, text: str) -> Path:
    (tmp_path / "main.tf").write_text(text, encoding="utf-8")
    return tmp_path


def test_repo_config_passes() -> None:
    assert cg.check_terraform(cg.INFRA) == []
    assert cg.check_deploy(cg.DEPLOY) == []


def test_good_terraform_passes(tmp_path: Path) -> None:
    assert cg.check_terraform(tf(tmp_path, GOOD_TF)) == []


def test_always_on_resources_fail(tmp_path: Path) -> None:
    text = GOOD_TF + 'resource "google_sql_database_instance" "db" {}\n'
    errors = cg.check_terraform(tf(tmp_path, text))
    assert errors == [
        "infra: google_sql_database_instance (Cloud SQL (use Neon, ADR-0003)) costs money at idle"
    ]


def test_min_instances_and_missing_guards_fail(tmp_path: Path) -> None:
    text = 'resource "google_artifact_registry_repository" "a" {}\nmin_instance_count = 1\n'
    errors = cg.check_terraform(tf(tmp_path, text))
    assert len(errors) == 3


def test_deploy_flags(tmp_path: Path) -> None:
    deploy = tmp_path / "deploy.yml"
    deploy.write_text("flags: --min-instances=1 --max-instances=10 --no-cpu-throttling\n")
    assert len(cg.check_deploy(deploy)) == 3
    deploy.write_text("flags: --min-instances=0 --max-instances=2\n")
    assert cg.check_deploy(deploy) == []
    deploy.write_text("flags: --cpu=1\n")
    assert len(cg.check_deploy(deploy)) == 2
    assert cg.check_deploy(tmp_path / "missing.yml") == []


def test_main_reports_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert cg.main() == 0
    monkeypatch.setattr(cg, "INFRA", tf(tmp_path, "min_instance_count = 2\n"))
    assert cg.main() == 1
