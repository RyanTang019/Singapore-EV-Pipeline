import re
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


def test_project_metadata_is_ready_for_public_use():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'description = "Add your description here"' not in pyproject
    assert '"pyyaml>=6"' in pyproject
