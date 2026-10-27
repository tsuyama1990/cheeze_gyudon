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


@pytest.mark.requirement("REQ-2026-010-F09")
def test_doctor_reports_each_missing_precondition(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L2-I30, L2-I43"""
    monkeypatch.chdir(root)
    runner = CliRunner()
    empty = runner.invoke(main, ["doctor"])
    assert empty.exit_code == 1
    assert empty.output.count("NG") == 4
    runner.invoke(main, ["init"])
    gate = root / "scripts" / "gate.sh"
    gate.parent.mkdir()
    gate.write_text("#!/usr/bin/env bash\n")
    gate.chmod(0o755)
    (root / ".pre-commit-config.yaml").write_text(HYGIENE_ONLY)
    commit(root, {})
    remote = root.parent / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)  # noqa: S603, S607
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    assert runner.invoke(main, ["doctor"]).exit_code == 0
    (root / ".pre-commit-config.yaml").write_text(HYGIENE_ONLY + "      - id: ruff\n")
    assert "ruff" in runner.invoke(main, ["doctor"]).output
    gate.chmod(0o644)
    assert runner.invoke(main, ["doctor"]).output.count("NG") == 2


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
