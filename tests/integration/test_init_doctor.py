import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from jtc_gov.adapters.cli import main, render_gitattributes, render_settings
from tests.integration.test_repo_git import commit, git, root  # noqa: F401

PROJECT = Path(__file__).parents[2]
HYGIENE_ONLY = """repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-yaml
"""


@pytest.mark.spec("L3-U46")
@pytest.mark.requirement("REQ-2026-010-F05")
def test_rendered_files() -> None:
    hooks = json.loads(render_settings())["hooks"]
    assert set(hooks) == {"PreToolUse", "SessionStart", "UserPromptSubmit"}
    commands = [h["command"] for group in hooks.values() for entry in group for h in entry["hooks"]]
    assert all("gov hook" in c for c in commands)
    assert ".specs/** text eol=lf" in render_gitattributes()


@pytest.mark.requirement("REQ-2026-010-F05")
def test_init_creates_is_idempotent_and_never_overwrites(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L2-I29, L2-I50"""
    monkeypatch.chdir(root)
    runner = CliRunner()
    assert runner.invoke(main, ["init"]).exit_code == 0
    assert (root / ".claude" / "settings.json").read_text() == render_settings()
    assert (root / ".gitattributes").read_text() == render_gitattributes()
    again = runner.invoke(main, ["init"])
    assert (again.exit_code, again.output) == (0, "")
    (root / ".gitattributes").write_text("* text=auto\n")
    clash = runner.invoke(main, ["init"])
    assert clash.exit_code == 1
    assert "text eol=lf" in clash.output
    assert (root / ".gitattributes").read_text() == "* text=auto\n"


@pytest.fixture
def healthy(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    monkeypatch.chdir(root)
    CliRunner().invoke(main, ["init"])
    gate = root / "scripts" / "gate.sh"
    gate.parent.mkdir()
    gate.write_text("#!/usr/bin/env bash\n")
    gate.chmod(0o755)
    (root / ".pre-commit-config.yaml").write_text(HYGIENE_ONLY)
    workflow = root / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("run: scripts/gate.sh\n")
    commit(root, {})
    remote = tmp_path_factory.mktemp("remote")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)  # noqa: S603, S607
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    return root


def failures(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("NG")]


@pytest.mark.requirement("REQ-2026-010-F09")
def test_doctor_reports_every_missing_precondition(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L2-I30"""
    monkeypatch.chdir(root)
    empty = CliRunner().invoke(main, ["doctor"])
    assert empty.exit_code == 1
    assert len(failures(empty.output)) == 5


@pytest.mark.requirement("REQ-2026-010-F09")
def test_doctor_passes_when_everything_is_wired(healthy: Path) -> None:
    assert CliRunner().invoke(main, ["doctor"]).exit_code == 0


@pytest.mark.requirement("REQ-2026-010-F09")
@pytest.mark.parametrize(
    ("path", "content", "broken"),
    [
        (".pre-commit-config.yaml", HYGIENE_ONLY + "      - id: ruff\n", "衛生フック"),
        (".github/workflows/ci.yml", "run: echo skipped\n", "CI のワークフロー"),
        (".github/workflows/ci.yml", "run: echo hi  # scripts/gate.sh\n", "CI のワークフロー"),
    ],
    ids=["duplicated-tools-in-pre-commit", "ci-does-not-call-the-gate", "gate-only-in-a-comment"],
)
def test_doctor_names_the_broken_wiring(
    healthy: Path, path: str, content: str, broken: str
) -> None:
    """L2-I43, L2-I54"""
    (healthy / path).write_text(content)
    found = failures(CliRunner().invoke(main, ["doctor"]).output)
    assert len(found) == 1
    assert broken in found[0]


@pytest.mark.requirement("REQ-2026-010-F09")
def test_doctor_fails_when_the_gate_is_not_executable(healthy: Path) -> None:
    (healthy / "scripts" / "gate.sh").chmod(0o644)
    assert len(failures(CliRunner().invoke(main, ["doctor"]).output)) == 1


@pytest.mark.requirement("REQ-2026-010-F09")
def test_this_repository_passes_doctor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(PROJECT)
    items = CliRunner().invoke(main, ["doctor"]).output.splitlines()
    assert [line for line in items if line.startswith("NG") and "origin/main" not in line] == []


@pytest.mark.requirement("REQ-2026-010-F09")
def test_gate_script_wiring() -> None:
    """L2-I39 to L2-I42 (static): the order of steps and the options of each tool."""
    text = (PROJECT / "scripts" / "gate.sh").read_text()
    order = ["ruff check", "mypy", "vulture", "pytest", "diff-cover", "gov check", "pre-commit run"]
    positions = [text.index(tool) for tool in order]
    assert positions == sorted(positions)
    assert "set -euo pipefail" in text
    assert text.count("${BASE}") >= 3
    assert "GATE_BASE:-origin/main" in text
    assert '--fail-under="${THRESHOLD}"' in text
    assert "--include-untracked" in text
    assert os.access(PROJECT / "scripts" / "gate.sh", os.X_OK)


@pytest.mark.requirement("REQ-2026-010-F09")
def test_ci_calls_only_the_gate() -> None:
    """L2-I44"""
    workflows = list((PROJECT / ".github" / "workflows").glob("*.yml"))
    assert workflows
    for path in workflows:
        spec = yaml.safe_load(path.read_text())
        jobs = spec["jobs"]
        assert "gate-verification" in jobs
        runs = [s["run"] for job in jobs.values() for s in job["steps"] if "run" in s]
        assert "scripts/gate.sh" in runs
        assert not [r for r in runs if any(t in r for t in ("ruff", "mypy", "pytest", "vulture"))]
        checkout = next(
            s for s in jobs["gate-verification"]["steps"] if "checkout" in s.get("uses", "")
        )
        assert checkout["with"]["fetch-depth"] == 0
        gate_step = next(
            s for s in jobs["gate-verification"]["steps"] if s.get("run") == "scripts/gate.sh"
        )
        assert "base_ref" in gate_step["env"]["GATE_BASE"]


@pytest.mark.requirement("REQ-2026-010-F09")
def test_doctor_outside_a_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["doctor"])
    assert result.exit_code == 1
    assert "E.repo" in result.output


@pytest.mark.requirement("REQ-2026-010-F09")
def test_ruleset_template_matches_the_design() -> None:
    """L1-C02: no approvals required, strict status checks, the CI job is the required check."""
    ruleset = json.loads((PROJECT / ".github" / "templates" / "ruleset_main.json").read_text())
    rules = {r["type"]: r.get("parameters", {}) for r in ruleset["rules"]}
    assert rules["pull_request"]["required_approving_review_count"] == 0
    assert rules["required_status_checks"]["strict_required_status_checks_policy"] is True
    contexts = [c["context"] for c in rules["required_status_checks"]["required_status_checks"]]
    workflow = yaml.safe_load(next((PROJECT / ".github" / "workflows").glob("*.yml")).read_text())
    assert set(contexts) <= set(workflow["jobs"])
    assert ruleset["conditions"]["ref_name"]["include"] == ["refs/heads/main"]


@pytest.mark.requirement("REQ-2026-010-F09")
def test_doctor_reads_yaml_workflows_and_survives_unreadable_ones(healthy: Path) -> None:
    """L2-I54"""
    workflows = healthy / ".github" / "workflows"
    (workflows / "ci.yml").rename(workflows / "ci.yaml")
    assert CliRunner().invoke(main, ["doctor"]).exit_code == 0
    (workflows / "binary.yml").write_bytes(b"\xff\xfe\x00")
    assert CliRunner().invoke(main, ["doctor"]).exit_code == 0
    (workflows / "ci.yaml").write_bytes(b"\xff\xfe\x00")
    result = CliRunner().invoke(main, ["doctor"])
    assert result.exit_code == 1
    assert len(failures(result.output)) == 1


@pytest.mark.requirement("REQ-2026-010-F05")
def test_init_outside_a_repo_reports_instead_of_crashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["init"])
    assert result.exit_code == 1
    assert "E.repo" in result.output


@pytest.mark.requirement("REQ-2026-010-F09")
@pytest.mark.spec("L2-I43")
@pytest.mark.parametrize("tool", ["mypy", "vulture", "pytest", "scripts/gate.sh", "gov check"])
def test_doctor_rejects_each_duplicated_tool_in_pre_commit(healthy: Path, tool: str) -> None:
    (healthy / ".pre-commit-config.yaml").write_text(
        HYGIENE_ONLY + f"      - id: x\n        entry: {tool}\n"
    )
    found = failures(CliRunner().invoke(main, ["doctor"]).output)
    assert len(found) == 1
    assert tool.rsplit("/", maxsplit=1)[-1] in found[0]


@pytest.mark.requirement("REQ-2026-010-F09")
@pytest.mark.spec("L2-I30")
@pytest.mark.parametrize(
    ("remove", "named"),
    [
        ("scripts/gate.sh", "scripts/gate.sh"),
        (".claude/settings.json", "settings.json"),
    ],
)
def test_doctor_reports_exactly_the_missing_file(healthy: Path, remove: str, named: str) -> None:
    (healthy / remove).unlink()
    found = failures(CliRunner().invoke(main, ["doctor"]).output)
    assert len(found) >= 1
    assert any(named in line for line in found)


@pytest.mark.requirement("REQ-2026-010-F09")
@pytest.mark.spec("L2-I30")
def test_doctor_reports_a_missing_origin_main(healthy: Path) -> None:
    git(healthy, "update-ref", "-d", "refs/remotes/origin/main")
    found = failures(CliRunner().invoke(main, ["doctor"]).output)
    assert len(found) == 1
    assert "origin/main" in found[0]
