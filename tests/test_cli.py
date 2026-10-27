import json
from pathlib import Path
from typing import Never

import pytest
from click.testing import CliRunner

from jtc_gov.cli import main as cli
from jtc_gov.domain.legacy_models import GateId, RequirementItem, RequirementStatus, StateModel
from jtc_gov.services.state_engine import is_path_unlocked


@pytest.fixture
def mock_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> StateModel:
    state_file = tmp_path / "state.json"
    monkeypatch.setattr("jtc_gov.services.state_engine.get_state_path", lambda: state_file)

    req = RequirementItem(
        title="Test",
        current_gate=GateId.GATE1_SPEC,
        status=RequirementStatus.IN_PROGRESS,
        unlocked_paths=[".specs/*"],
        completed_gates=[],
    )
    state = StateModel(active_requirement_id="REQ-2026-001", requirements={"REQ-2026-001": req})
    from jtc_gov.services.state_engine import write_state

    write_state(state)

    monkeypatch.chdir(tmp_path)
    return state


@pytest.mark.requirement("REQ-2026-001-F04")
def test_verify_tool_unauthorized_edit(mock_state: StateModel) -> None:
    # Active gate is GATE1_SPEC, unlocked_paths is [".specs/*"]
    # Attempting to edit "src/service.py"

    runner = CliRunner()
    payload = {"path": "src/service.py"}

    result = runner.invoke(cli, ["verify-tool", "--tool", "Edit", "--input", json.dumps(payload)])

    assert result.exit_code == 1
    assert "[GOVERNANCE ERROR]" in result.output
    assert "blocked in GATE1_SPEC" in result.output
    assert "src/service.py" in result.output


@pytest.mark.requirement("REQ-2026-001-F04")
def test_verify_tool_authorized_edit(mock_state: StateModel) -> None:
    # Edit .specs/ file should pass
    runner = CliRunner()
    payload = {"path": ".specs/01_req_spec.md"}

    result = runner.invoke(cli, ["verify-tool", "--tool", "Edit", "--input", json.dumps(payload)])

    assert result.exit_code == 0
    assert result.output == ""


@pytest.mark.requirement("REQ-2026-001-F04")
def test_verify_tool_not_edit(mock_state: StateModel) -> None:
    # Non-edit tool should be ignored
    runner = CliRunner()
    payload = {"path": "src/service.py"}

    result = runner.invoke(cli, ["verify-tool", "--tool", "Bash", "--input", json.dumps(payload)])

    assert result.exit_code == 0
    assert result.output == ""


@pytest.mark.requirement("REQ-2026-001-F04")
def test_verify_tool_invalid_json(mock_state: StateModel) -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["verify-tool", "--tool", "Edit", "--input", "invalid json"])

    assert result.exit_code == 1
    assert "Tool payload is not valid JSON." in result.output


@pytest.mark.requirement("REQ-2026-001-F04")
def test_verify_tool_no_path(mock_state: StateModel) -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["verify-tool", "--tool", "Edit", "--input", "{}"])

    assert result.exit_code == 1
    assert "Could not determine file path from tool payload." in result.output


@pytest.mark.requirement("REQ-2026-001-F04")
def test_verify_tool_notebook_path(mock_state: StateModel) -> None:
    runner = CliRunner()
    payload = {"notebook_path": "src/nb.ipynb"}

    result = runner.invoke(
        cli, ["verify-tool", "--tool", "NotebookEdit", "--input", json.dumps(payload)]
    )

    assert result.exit_code == 1
    assert "blocked in GATE1_SPEC" in result.output
    assert "src/nb.ipynb" in result.output


@pytest.mark.requirement("REQ-2026-001-F01")
def test_is_path_unlocked_absolute_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = str(tmp_path / "doc" / "notes.md")
    assert is_path_unlocked(target, ["doc/*"]) is True


@pytest.mark.requirement("REQ-2026-001-F01")
def test_is_path_unlocked_absolute_locked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = str(tmp_path / "src" / "module.py")
    assert is_path_unlocked(target, ["doc/*"]) is False


@pytest.mark.requirement("REQ-2026-001-F01")
def test_is_path_unlocked_outside_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    outside = str(tmp_path.parent / "elsewhere" / "file.py")
    assert is_path_unlocked(outside, ["*"]) is False


@pytest.mark.requirement("REQ-2026-001-F01")
def test_is_path_unlocked_traversal_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert is_path_unlocked("../secret.py", ["*"]) is False


@pytest.mark.requirement("REQ-2026-001-F04")
def test_verify_tool_missing_active_req(mock_state: StateModel) -> None:
    from jtc_gov.services.state_engine import read_state, write_state

    state = read_state()
    state_dict = state.model_dump()
    state_dict["active_requirement_id"] = "REQ-NOT-FOUND"
    write_state(StateModel.model_validate(state_dict))

    runner = CliRunner()
    payload = {"path": "src/service.py"}

    result = runner.invoke(cli, ["verify-tool", "--tool", "Edit", "--input", json.dumps(payload)])

    assert result.exit_code == 1
    assert "Active requirement 'REQ-NOT-FOUND' not found in state." in result.output


@pytest.mark.requirement("REQ-2026-001-F03")
def test_cli_trace_check(mock_state: StateModel) -> None:
    Path(".specs/REQ-2026-001").mkdir(parents=True)
    Path("tests").mkdir()
    Path(".specs/REQ-2026-001/01_req_spec.md").write_text("[REQ-2026-001-F01]")
    Path("tests/test_x.py").write_text(
        '@pytest.mark.requirement("REQ-2026-001-F01")\ndef test_x(): pass'
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["trace-check"])

    assert result.exit_code == 0
    assert "Traceability check passed" in result.output


@pytest.mark.requirement("REQ-2026-001-F05")
def test_cli_escalate(mock_state: StateModel) -> None:
    from jtc_gov.services.state_engine import read_state, write_state

    # Setup state to GATE5_IMPL
    state = read_state()
    req_dict = state.requirements["REQ-2026-001"].model_dump()
    req_dict["current_gate"] = GateId.GATE5_IMPL
    req_dict["completed_gates"] = [
        GateId.GATE1_SPEC,
        GateId.GATE2_SYSTEM,
        GateId.GATE3_INTEGRATION,
        GateId.GATE4_DETAIL,
    ]
    state_dict = state.model_dump()
    state_dict["requirements"]["REQ-2026-001"] = req_dict
    write_state(StateModel.model_validate(state_dict))

    runner = CliRunner()
    result = runner.invoke(cli, ["escalate", "--gate", "2", "--reason", "API contract change"])

    assert result.exit_code == 0
    assert "Escalated to Gate 2" in result.output

    # Check that it reverted
    new_state = read_state()
    assert new_state.requirements["REQ-2026-001"].current_gate == GateId.GATE2_SYSTEM

    # Check unlocked paths re-locked
    paths = new_state.requirements["REQ-2026-001"].unlocked_paths
    # Only 02_ is unlocked for GATE2_SYSTEM
    assert any("02_" in p for p in paths)
    assert not any("src/*" in p for p in paths)


@pytest.mark.requirement("REQ-2026-001-F01")
def test_cli_status(mock_state: StateModel) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "Active Requirement: REQ-2026-001 - Test" in result.output
    assert "Current Gate:       GATE1_SPEC" in result.output


@pytest.mark.requirement("REQ-2026-001-F01")
def test_cli_status_missing_req(mock_state: StateModel) -> None:
    from jtc_gov.services.state_engine import read_state, write_state

    state = read_state()
    state_dict = state.model_dump()
    state_dict["active_requirement_id"] = "REQ-NOT-FOUND"
    write_state(StateModel.model_validate(state_dict))

    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 1
    assert "Active requirement 'REQ-NOT-FOUND' not found in state." in result.output


@pytest.mark.requirement("REQ-2026-001-F02")
def test_cli_gate_check(mock_state: StateModel) -> None:
    # Setup everything for gate 1 success
    Path(".specs/REQ-2026-001").mkdir(parents=True)
    Path(".specs/REQ-2026-001/01_req_spec.md").touch()
    Path(".specs/REQ-2026-001/01_acceptance_tests.feature").touch()
    review_dir = Path(".specs/REQ-2026-001/reviews")
    review_dir.mkdir()

    review_data: dict[str, object] = {
        "gate_id": "GATE1_SPEC",
        "requirement_id": "REQ-2026-001",
        "reviewer_persona": "LEGAL",
        "status": "APPROVED",
        "design_flaws": [],
        "test_design_flaws": [],
        "accepted_tradeoffs": [],
        "reviewed_at": "2023-01-01T00:00:00Z",
    }
    review_dir.joinpath("review.json").write_text(json.dumps(review_data))

    runner = CliRunner()
    result = runner.invoke(cli, ["gate-check", "--gate", "1"])
    assert result.exit_code == 0
    assert "Gate 1 check passed. State advanced." in result.output


@pytest.mark.requirement("REQ-2026-001-F02")
def test_cli_gate_check_fails(mock_state: StateModel) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["gate-check", "--gate", "6"])
    assert result.exit_code == 1
    assert "Gate must be 1-5" in result.output


@pytest.mark.requirement("REQ-2026-001-F02")
def test_cli_gate_check_error(mock_state: StateModel) -> None:
    runner = CliRunner()
    # No files exist
    result = runner.invoke(cli, ["gate-check", "--gate", "1"])
    assert result.exit_code == 1
    assert "[GOVERNANCE ERROR]" in result.output


@pytest.mark.requirement("REQ-2026-001-F03")
def test_cli_trace_check_error(mock_state: StateModel) -> None:
    runner = CliRunner()
    # Trace check should fail with missing files
    result = runner.invoke(cli, ["trace-check"])
    assert result.exit_code == 1
    assert "[GOVERNANCE ERROR]" in result.output


@pytest.mark.requirement("REQ-2026-001-F05")
def test_cli_escalate_error(mock_state: StateModel) -> None:
    runner = CliRunner()
    # Escalate should fail due to invalid target gate logic
    result = runner.invoke(cli, ["escalate", "--gate", "3", "--reason", "Reason"])
    assert result.exit_code == 1
    assert "[GOVERNANCE ERROR]" in result.output


@pytest.mark.requirement("REQ-2026-001-F01")
def test_audit_push(mock_state: StateModel, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    # Mock subprocess.run for pytest
    def mock_run(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(subprocess, "run", mock_run)

    # Mock verify_traceability to pass
    monkeypatch.setattr("jtc_gov.cli.verify_traceability", lambda: None)

    runner = CliRunner()
    result = runner.invoke(cli, ["audit-push"])
    assert result.exit_code == 0
    assert "Local CI validation passed." in result.output


@pytest.mark.requirement("REQ-2026-001-F01")
def test_audit_push_fails(mock_state: StateModel, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    # Mock subprocess.run for pytest
    def mock_run(*args: object, **kwargs: object) -> Never:
        raise subprocess.CalledProcessError(1, "cmd")

    monkeypatch.setattr(subprocess, "run", mock_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["audit-push"])
    assert result.exit_code == 1
    assert "Local CI failed" in result.output
