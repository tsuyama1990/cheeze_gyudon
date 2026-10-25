"""Test tautological testing interception."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.cli import verify_tool


@pytest.mark.requirement("REQ-2026-004-F01")
def test_tautological_testing_interception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates agent attempting to alter test assertions while src/ is locked -> Intercepted."""
    monkeypatch.chdir(tmp_path)

    # Setup initial state where src/ is locked
    specs_dir = Path(".specs")
    specs_dir.mkdir()
    state_file = specs_dir / "state.json"

    state_data = {
        "active_requirement_id": "REQ-123",
        "requirements": {
            "REQ-123": {
                "title": "t",
                "current_gate": "GATE1_SPEC",
                "status": "IN_PROGRESS",
                "unlocked_paths": [".specs/REQ-123/*"],
                "completed_gates": [],
            }
        },
    }
    state_file.write_text(json.dumps(state_data))

    runner = CliRunner()

    # Agent tries to write to a test file in src/ or tests/
    tool_input = json.dumps({"file_path": "tests/test_logic.py"})
    result = runner.invoke(verify_tool, ["--input", tool_input])

    # Must be intercepted (exit code 1)
    assert result.exit_code == 1
    assert "Access denied" in result.output
    assert "'tests/test_logic.py' is locked" in result.output
