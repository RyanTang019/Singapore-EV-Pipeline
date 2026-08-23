import os
import re
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PUSH_TO_MAIN = "github.event_name == 'push' && github.ref == 'refs/heads/main'"


def load_workflow(name: str) -> dict:
    """Load a workflow without YAML 1.1 coercing the `on` key to a boolean."""

    workflow_path = REPO_ROOT / ".github" / "workflows" / name
    return yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def normalized_condition(job: dict) -> str:
    """Collapse GitHub expression whitespace for stable security assertions."""

    return " ".join(job.get("if", "").split())


def test_ci_separates_untrusted_and_gcp_backed_jobs():
    workflow = load_workflow("ci.yml")
    jobs = workflow["jobs"]

    assert {"static", "warehouse"} <= jobs.keys()
    assert jobs["static"]["permissions"] == {"contents": "read"}
    assert "id-token" not in jobs["static"]["permissions"]

    warehouse = jobs["warehouse"]
    assert warehouse["needs"] == "static"
    assert PUSH_TO_MAIN in normalized_condition(warehouse)
    assert warehouse["permissions"] == {"contents": "read", "id-token": "write"}


def test_terraform_separates_untrusted_validation_from_prod_jobs():
    workflow = load_workflow("terraform.yml")
    jobs = workflow["jobs"]

    assert {"validate", "plan", "apply"} <= jobs.keys()
    assert jobs["validate"]["permissions"] == {"contents": "read"}
    assert "id-token" not in jobs["validate"]["permissions"]

    for job_name in ("plan", "apply"):
        job = jobs[job_name]
        assert PUSH_TO_MAIN in normalized_condition(job)
        assert job["permissions"] == {"contents": "read", "id-token": "write"}

    assert jobs["plan"]["needs"] == "validate"
    assert jobs["apply"]["needs"] == "plan"
    assert jobs["apply"]["environment"] == "production"


def test_deploy_job_uses_protected_production_environment():
    workflow = load_workflow("deploy.yml")
    deploy = workflow["jobs"]["deploy"]

    assert deploy["environment"] == "production"
    assert deploy["permissions"] == {"contents": "read"}


def test_codeowners_requires_maintainer_review_for_sensitive_paths():
    codeowners = (REPO_ROOT / ".github" / "CODEOWNERS").read_text(
        encoding="utf-8"
    )
    rules = [
        line.split()
        for raw_line in codeowners.splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    ]
    expected_patterns = {
        "/.github/CODEOWNERS",
        "/.github/workflows/",
        "/terraform/",
        "/Dockerfile*",
        "/.dockerignore",
        "/pyproject.toml",
        "/uv.lock",
        "/docker-compose.yml",
        "/dagster.yaml",
        "/workspace.yaml",
        "/transform/profiles.yml",
        "/transform/dbt_project.yml",
        "/transform/macros/",
        "/transform/models/staging/sources.yml",
        "/src/orchestrate/defs/transform/",
    }

    assert {rule[0] for rule in rules} == expected_patterns
    assert all(rule[1:] == ["@RyanTang019", "@oliverlrj"] for rule in rules)


def test_wif_providers_only_accept_pushes_to_main():
    identity = (REPO_ROOT / "terraform" / "prod" / "identity.tf").read_text(
        encoding="utf-8"
    )

    assert identity.count("assertion.event_name == 'push'") == 2
    assert identity.count("assertion.ref == 'refs/heads/main'") == 2


def test_public_tree_excludes_vendored_terraform_skill_and_tracks_assets():
    vendored_skill = REPO_ROOT / ".claude" / "skills" / "terraform-skill"
    assets_placeholder = REPO_ROOT / "assets" / ".gitkeep"
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert not any(path.is_file() for path in vendored_skill.rglob("*"))
    assert ".claude/skills/terraform-skill/" in gitignore.splitlines()
    assert assets_placeholder.is_file()


def test_readme_is_self_contained_for_public_readers():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert not re.findall(r"docs/[A-Za-z0-9_./-]+\.md", readme)
    assert "## Project status" in readme
    assert "## Roadmap" not in readme


def test_readme_onboarding_uses_reader_owned_gcp_project():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    onboarding = readme.split("## Infrastructure", maxsplit=1)[0]
    local_development = readme.split(
        "### Local development — environment selection", maxsplit=1
    )[1].split("### VM", maxsplit=1)[0]

    assert "sg-pipeline-dev" not in onboarding
    assert "sg-pipeline-dev" not in local_development
    assert "Ask a project admin" not in onboarding
    assert "GCP_PROJECT_ID=your-gcp-project-id" in onboarding
    assert "gcloud services enable bigquery.googleapis.com" in onboarding
    assert "bq --location=asia-southeast1 mk --dataset" in onboarding


def test_project_metadata_is_ready_for_public_use():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'description = "Add your description here"' not in pyproject
    assert '"pyyaml>=6"' in pyproject


def load_env_example() -> dict[str, str]:
    values = {}
    for raw_line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        assignment = line.split("#", 1)[0].strip()
        key, value = assignment.split("=", 1)
        values[key] = value.strip().strip("'\"")
    return values


def test_env_example_uses_reader_owned_placeholders_and_safe_defaults():
    env = load_env_example()

    assert env["GCP_PROJECT_ID"] == "your-gcp-project-id"
    assert env["DEV_SCHEMA_PREFIX"] == "dev_yourhandle"
    assert env["LTA_API_KEY"] == "your_lta_api_key"
    assert env["GCP_REGION"] == "asia-southeast1"
    assert env["BQ_DATASET_RAW"] == "dev_raw"


def run_setup_with_platform(tmp_path: Path, platform: str) -> subprocess.CompletedProcess[str]:
    fake_uname = tmp_path / "uname"
    fake_uname.write_text(f"#!/bin/sh\nprintf '%s\\n' '{platform}'\n", encoding="utf-8")
    fake_uname.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:/usr/bin:/bin"
    return subprocess.run(
        ["/bin/sh", str(REPO_ROOT / "bin" / "setup")],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )


def test_setup_rejects_non_macos_before_installing_tools(tmp_path):
    result = run_setup_with_platform(tmp_path, "Linux")

    assert result.returncode == 1
    assert "macOS" in result.stderr
    assert "Homebrew" in result.stderr


def test_setup_explains_when_homebrew_is_missing(tmp_path):
    result = run_setup_with_platform(tmp_path, "Darwin")

    assert result.returncode == 1
    assert "Homebrew is required" in result.stderr
