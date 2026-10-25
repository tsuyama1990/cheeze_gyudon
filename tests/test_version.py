# ruff: noqa: E501
"""Comprehensive unit tests for jtc_gov package and CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov import __version__
from jtc_gov.cli import (
    main,
)
from jtc_gov.services.state_engine import is_path_unlocked


@pytest.mark.requirement("REQ-INIT-001")
def test_version() -> None:
    """Verify package version."""
    assert __version__ == "0.1.0"


@pytest.mark.requirement("REQ-INIT-001")
def test_cli_version() -> None:
    """Verify CLI version option."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


@pytest.mark.requirement("REQ-INIT-001")
def test_cli_status() -> None:
    """Verify CLI status subcommand."""
    runner = CliRunner()
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "Active Requirement:" in result.output


@pytest.mark.requirement("REQ-INIT-001")
def test_is_path_unlocked() -> None:
    """Verify path unlocking glob matching."""
    patterns = [".specs/REQ-2026-001/01_*", "doc/*", "README.md"]
    assert is_path_unlocked(".specs/REQ-2026-001/01_req_spec.md", patterns) is True
    assert is_path_unlocked(r".specs\REQ-2026-001\01_req_spec.md", patterns) is True
    assert is_path_unlocked("./doc/jtc_governance_framework.md", patterns) is True
    assert is_path_unlocked("README.md", patterns) is True
    assert is_path_unlocked("src/jtc_gov/forbidden.py", patterns) is False


@pytest.mark.requirement("REQ-INIT-001")
def test_verify_tool_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify verify-tool allows unlocked path."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    Path(".specs").mkdir()
    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE1_SPEC", "status": "IN_PROGRESS", "unlocked_paths": ["README.md"], "completed_gates": []}}}'
    )
    result = runner.invoke(main, ["verify-tool", "--file", "README.md"])
    assert result.exit_code == 0


@pytest.mark.requirement("REQ-INIT-001")
def test_verify_tool_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify verify-tool intercepts locked path with exit code 1."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    Path(".specs").mkdir()
    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE1_SPEC", "status": "IN_PROGRESS", "unlocked_paths": ["README.md"], "completed_gates": []}}}'
    )
    result = runner.invoke(main, ["verify-tool", "--file", "src/forbidden.py"])
    assert result.exit_code == 1
    assert "Access denied" in result.output


@pytest.mark.requirement("REQ-INIT-001")
def test_verify_tool_via_json_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify verify-tool parses tool input JSON and blocks unauthorized file."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    Path(".specs").mkdir()
    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE1_SPEC", "status": "IN_PROGRESS", "unlocked_paths": ["README.md"], "completed_gates": []}}}'
    )
    result = runner.invoke(
        main,
        ["verify-tool", "--tool", "Edit", "--input", '{"file_path": "src/bad.py"}'],
    )
    assert result.exit_code == 1
    assert "Access denied" in result.output


@pytest.mark.requirement("REQ-INIT-001")
def test_verify_tool_no_target_file() -> None:
    """Verify verify-tool passes when no file is targeted."""
    runner = CliRunner()
    result = runner.invoke(main, ["verify-tool", "--tool", "Bash", "--input", '{"command": "ls"}'])
    assert result.exit_code == 0


@pytest.mark.requirement("REQ-INIT-001")
def test_verify_tool_missing_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify verify-tool gracefully passes if state.json does not exist."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["verify-tool", "--file", "any_file.py"])
    assert result.exit_code == 0


@pytest.mark.requirement("REQ-INIT-001")
def test_is_path_unlocked_absolute_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Absolute paths inside the root that match a pattern are allowed."""
    monkeypatch.chdir(tmp_path)
    target = str(tmp_path / "doc" / "notes.md")
    assert is_path_unlocked(target, ["doc/*"]) is True


@pytest.mark.requirement("REQ-INIT-001")
def test_is_path_unlocked_absolute_locked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Absolute paths inside the root that do not match are denied."""
    monkeypatch.chdir(tmp_path)
    target = str(tmp_path / "src" / "module.py")
    assert is_path_unlocked(target, ["doc/*"]) is False


@pytest.mark.requirement("REQ-INIT-001")
def test_is_path_unlocked_outside_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Paths outside the project root are always denied."""
    monkeypatch.chdir(tmp_path)
    outside = str(tmp_path.parent / "elsewhere" / "file.py")
    assert is_path_unlocked(outside, ["*"]) is False


@pytest.mark.requirement("REQ-INIT-001")
def test_is_path_unlocked_traversal_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`..` traversal escaping the root is denied even if a glob would match."""
    monkeypatch.chdir(tmp_path)
    assert is_path_unlocked("../secret.py", ["*"]) is False


@pytest.mark.requirement("REQ-INIT-001")
def test_verify_tool_notebook_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """verify-tool resolves notebook_path from tool input JSON."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    Path(".specs").mkdir()
    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE1_SPEC", "status": "IN_PROGRESS", "unlocked_paths": ["README.md"], "completed_gates": []}}}'
    )
    result = runner.invoke(
        main,
        ["verify-tool", "--tool", "NotebookEdit", "--input", '{"notebook_path": "src/nb.ipynb"}'],
    )
    assert result.exit_code == 1
    assert "Access denied" in result.output
