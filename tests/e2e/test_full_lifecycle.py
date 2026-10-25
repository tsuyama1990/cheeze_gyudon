"""Full V-Model E2E Simulation Test."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.cli import (
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

    # 1. Initialize repo via gov init
    result = runner.invoke(init)
    assert result.exit_code == 0
    assert Path(".specs/state.json").exists()
    assert Path(".agent/settings.json").exists()

    # 2. Verify unauthorized src/ edit attempt in Gate 1 is blocked
    tool_input = json.dumps({"file_path": "src/module.py"})
    result = runner.invoke(verify_tool, ["--input", tool_input])
    assert result.exit_code == 1
    assert "src/module.py" in result.output
    assert "GATE1_SPEC" in result.output

    # 3. Formulate Gate 1 spec and acceptance test scenarios
    spec_dir = Path(".specs/REQ-0000-001")
    spec_dir.mkdir(parents=True)
    (spec_dir / "01_req_spec.md").write_text("# Spec\n- [REQ-0000-001-F01] run", encoding="utf-8")
    (spec_dir / "01_acceptance_tests.feature").write_text("Feature: x", encoding="utf-8")

    # 4. Run Gate 1 check: gov gate-check --gate 1 -> Advances to Gate 2
    result = runner.invoke(gate_check, ["--gate", "1"])
    assert result.exit_code == 0
    assert "Gate 1 check passed. State advanced." in result.output

    state_data = json.loads(Path(".specs/state.json").read_text(encoding="utf-8"))
    assert state_data["requirements"]["REQ-0000-001"]["current_gate"] == "GATE2_SYSTEM"

    # 5. Gate 2 deliverables
    (spec_dir / "02_system_design.md").write_text("# System", encoding="utf-8")
    (spec_dir / "02_system_tests.md").write_text("# System tests", encoding="utf-8")
    result = runner.invoke(gate_check, ["--gate", "2"])
    assert result.exit_code == 0
    state_data = json.loads(Path(".specs/state.json").read_text(encoding="utf-8"))
    assert state_data["requirements"]["REQ-0000-001"]["current_gate"] == "GATE3_INTEGRATION"

    # 6. Gate 3 deliverables
    (spec_dir / "03_architecture.md").write_text("# Arch", encoding="utf-8")
    (spec_dir / "03_integration_tests.md").write_text("# Integration", encoding="utf-8")
    result = runner.invoke(gate_check, ["--gate", "3"])
    assert result.exit_code == 0
    state_data = json.loads(Path(".specs/state.json").read_text(encoding="utf-8"))
    assert state_data["requirements"]["REQ-0000-001"]["current_gate"] == "GATE4_DETAIL"

    # 7. Gate 4 deliverables: detail design + test file + human sign-off
    (spec_dir / "04_detail_design.md").write_text("# Detail", encoding="utf-8")
    tests_dir = Path("tests")
    tests_dir.mkdir()
    (tests_dir / "test_module.py").write_text(
        "import pytest\n\n"
        '@pytest.mark.requirement("REQ-0000-001-F01")\n'
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    (spec_dir / "05_decision.md").write_text("HUMAN_SIGN_OFF: APPROVED\n", encoding="utf-8")

    result = runner.invoke(gate_check, ["--gate", "4"])
    assert result.exit_code == 0
    state_data = json.loads(Path(".specs/state.json").read_text(encoding="utf-8"))
    assert state_data["requirements"]["REQ-0000-001"]["current_gate"] == "GATE5_IMPL"

    # 8. src/ is now unlocked for writing
    result = runner.invoke(verify_tool, ["--input", tool_input])
    assert result.exit_code == 0

    # 9. Implement code in src/ (simulated)
    src_dir = Path("src")
    src_dir.mkdir()
    (src_dir / "module.py").write_text("def run(): pass\n", encoding="utf-8")

    # 10. Verify gov trace-check passes with zero under-coverage
    result = runner.invoke(trace_check)
    assert result.exit_code == 0
    assert "Traceability check passed." in result.output

    # 11. Simulate Reverse Escalation: gov escalate --gate 2 --reason "Upstream API flaw"
    result = runner.invoke(escalate, ["--gate", "2", "--reason", "Upstream API flaw"])
    assert result.exit_code == 0
    assert "Escalated to Gate 2." in result.output

    # Confirm src/ is instantly re-locked
    state_data = json.loads(Path(".specs/state.json").read_text(encoding="utf-8"))
    assert state_data["requirements"]["REQ-0000-001"]["current_gate"] == "GATE2_SYSTEM"

    result = runner.invoke(verify_tool, ["--input", tool_input])
    assert result.exit_code == 1
    assert "src/module.py" in result.output
    assert "GATE2_SYSTEM" in result.output
