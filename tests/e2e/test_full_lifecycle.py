"""Full V-Model E2E Simulation Test."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.cli import (
    draft_decision,
    escalate,
    gate_check,
    init,
    trace_check,
    verify_tool,
)


@pytest.mark.requirement("REQ-2026-004-F06")
def test_full_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: PLR0915
    """Simulate a complete agent lifecycle."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # 1. Initialize repo via gov init --preset solo
    result = runner.invoke(init, ["--preset", "solo"])
    assert result.exit_code == 0
    assert Path(".specs/state.json").exists()
    assert Path(".agent/settings.json").exists()

    # Need to update state.json active_requirement_id to REQ-INIT-001 for test consistency
    # (init defaults to REQ-INIT-001, so we are good)

    # 2. Verify unauthorized src/ edit attempt in Gate 1 is blocked
    tool_input = json.dumps({"file_path": "src/module.py"})
    result = runner.invoke(verify_tool, ["--input", tool_input])
    assert result.exit_code == 1
    assert "Access denied: 'src/module.py' is locked" in result.output

    # 3. Formulate Gate 1 spec and acceptance test scenarios
    spec_dir = Path(".specs/REQ-INIT-001")
    spec_dir.mkdir(parents=True)
    (spec_dir / "01_req_spec.md").write_text("# Spec", encoding="utf-8")

    # 4. Run Gate 1 check: gov gate-check --gate 1 -> Advances to Gate 2
    result = runner.invoke(gate_check, ["--gate", "1"])
    assert result.exit_code == 0
    assert "Gate 1 passed. Promoted to GATE2_SPEC." in result.output

    state_data = json.loads(Path(".specs/state.json").read_text(encoding="utf-8"))
    assert state_data["requirements"]["REQ-INIT-001"]["current_gate"] == "GATE2_SPEC"

    # 5. Progress through Gate 2, 3, 4
    result = runner.invoke(gate_check, ["--gate", "2"])
    assert result.exit_code == 0
    result = runner.invoke(gate_check, ["--gate", "3"])
    assert result.exit_code == 0
    result = runner.invoke(gate_check, ["--gate", "4"])
    assert result.exit_code == 0

    state_data = json.loads(Path(".specs/state.json").read_text(encoding="utf-8"))
    assert state_data["requirements"]["REQ-INIT-001"]["current_gate"] == "GATE4.5_DECISION"

    # 6. Generate Tri-Polar decision: gov draft-decision
    result = runner.invoke(draft_decision)
    assert result.exit_code == 0
    assert "Decision approved. Promoted to GATE5_IMPLEMENTATION. src/ is unlocked." in result.output

    state_data = json.loads(Path(".specs/state.json").read_text(encoding="utf-8"))
    assert state_data["requirements"]["REQ-INIT-001"]["current_gate"] == "GATE5_IMPLEMENTATION"
    assert (Path(".specs/REQ-INIT-001/05_decision.md")).exists()

    # Verify src/ is now unlocked for writing
    result = runner.invoke(verify_tool, ["--input", tool_input])
    assert result.exit_code == 0

    # 7. Implement code in src/ and tests in tests/ (simulated)
    src_dir = Path("src")
    src_dir.mkdir()
    (src_dir / "module.py").write_text("def run(): pass\n", encoding="utf-8")

    # 8. Verify gov trace-check passes with zero under-coverage
    result = runner.invoke(trace_check)
    assert result.exit_code == 0
    assert "100% REQ-to-test AST alignment" in result.output

    # 9. Simulate Reverse Escalation: gov escalate --gate 2 --reason "Upstream API flaw"
    result = runner.invoke(escalate, ["--gate", "2", "--reason", "Upstream API flaw"])
    assert result.exit_code == 0
    assert "Escalated to GATE2_SPEC: Upstream API flaw. Workspace re-locked." in result.output

    # Confirm src/ is instantly re-locked
    state_data = json.loads(Path(".specs/state.json").read_text(encoding="utf-8"))
    assert state_data["requirements"]["REQ-INIT-001"]["current_gate"] == "GATE2_SPEC"

    result = runner.invoke(verify_tool, ["--input", tool_input])
    assert result.exit_code == 1
    assert "Access denied: 'src/module.py' is locked" in result.output

    # 10. (In the actual E2E suite, this step is verified by run_verify_all script outside)
