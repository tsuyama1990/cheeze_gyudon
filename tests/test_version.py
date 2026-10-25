"""Comprehensive unit tests for jtc_gov package and CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov import __version__
from jtc_gov.cli import (
    extract_target_file,
    is_path_unlocked,
    main,
)


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
def test_extract_target_file() -> None:
    """Verify file extraction from various input formats."""
    assert extract_target_file(None, "direct_file.py") == "direct_file.py"
    assert extract_target_file('{"file_path": "path/to/file.py"}', None) == "path/to/file.py"
    assert extract_target_file('{"target_file": "path/to/target.py"}', None) == "path/to/target.py"
    assert extract_target_file("invalid json", None) is None
    assert extract_target_file("[]", None) is None
    assert extract_target_file(None, None) is None


@pytest.mark.requirement("REQ-INIT-001")
def test_verify_tool_allowed() -> None:
    """Verify verify-tool allows unlocked path."""
    runner = CliRunner()
    result = runner.invoke(main, ["verify-tool", "--file", "README.md"])
    assert result.exit_code == 0


@pytest.mark.requirement("REQ-INIT-001")
def test_verify_tool_denied() -> None:
    """Verify verify-tool intercepts locked path with exit code 1."""
    runner = CliRunner()
    result = runner.invoke(main, ["verify-tool", "--file", "src/forbidden.py"])
    assert result.exit_code == 1
    assert "Access denied" in result.output


@pytest.mark.requirement("REQ-INIT-001")
def test_verify_tool_via_json_input() -> None:
    """Verify verify-tool parses tool input JSON and blocks unauthorized file."""
    runner = CliRunner()
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
