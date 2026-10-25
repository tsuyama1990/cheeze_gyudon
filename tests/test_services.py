import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jtc_gov.domain.exceptions import GateCheckFailedError, TraceabilityMismatchError
from jtc_gov.domain.models import GateId, RequirementItem, RequirementStatus, StateModel
from jtc_gov.services.escalator import escalate
from jtc_gov.services.gate_keeper import get_unlocked_paths_for_gate, validate_gate
from jtc_gov.services.tracer import (
    extract_requirements_from_spec,
    extract_requirements_from_tests,
    verify_traceability,
)


@pytest.fixture
def mock_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> StateModel:
    state_file = tmp_path / "state.json"
    monkeypatch.setattr("jtc_gov.services.state_engine.get_state_path", lambda: state_file)

    # Mock CWD logic for tracer/gatekeeper
    monkeypatch.chdir(tmp_path)
    Path(".specs/REQ-2026-001").mkdir(parents=True)
    Path("tests").mkdir()

    # Needs to match pattern r"^REQ-\d{4}-\d{3,}$" for requirement_id
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

    return state


@pytest.mark.requirement("REQ-2026-001-F03")
def test_tracer_extraction(tmp_path: Path) -> None:
    spec_file = tmp_path / "01_req_spec.md"
    spec_file.write_text("# Test\n- [REQ-2026-001-F01] is a req\n- [REQ-2026-002] another")

    reqs = extract_requirements_from_spec(spec_file)
    assert reqs == {"REQ-2026-001-F01", "REQ-2026-002"}

    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    test_file = test_dir / "test_something.py"
    test_file.write_text("""
import pytest
@pytest.mark.requirement("REQ-2026-001-F01")
def test_a(): pass

@pytest.mark.requirement("REQ-2026-002")
def test_b(): pass
""")

    test_reqs = extract_requirements_from_tests(test_dir)
    assert test_reqs == {"REQ-2026-001-F01", "REQ-2026-002"}

    # syntax error file ignored
    bad_file = test_dir / "bad.py"
    bad_file.write_text("def def def syntax error")
    assert extract_requirements_from_tests(test_dir) == {"REQ-2026-001-F01", "REQ-2026-002"}


@pytest.mark.requirement("REQ-2026-001-F03")
def test_verify_traceability(mock_state: StateModel) -> None:
    # Setup matching files
    Path(".specs/REQ-2026-001/01_req_spec.md").write_text("[REQ-2026-001-F01]")
    Path("tests/test_x.py").write_text(
        '@pytest.mark.requirement("REQ-2026-001-F01")\ndef test_x(): pass'
    )

    verify_traceability()

    # Setup missing in tests
    Path(".specs/REQ-2026-001/01_req_spec.md").write_text("[REQ-2026-001-F01]\n[REQ-2026-001-F02]")
    with pytest.raises(
        TraceabilityMismatchError, match="Missing test coverage for: REQ-2026-001-F02"
    ):
        verify_traceability()

    # Setup missing in spec
    Path(".specs/REQ-2026-001/01_req_spec.md").write_text("[REQ-2026-001-F01]")
    Path("tests/test_y.py").write_text(
        '@pytest.mark.requirement("REQ-2026-001-F03")\ndef test_y(): pass'
    )
    with pytest.raises(
        TraceabilityMismatchError, match="Scope creep / undefined in spec: REQ-2026-001-F03"
    ):
        verify_traceability()

    # Missing spec
    Path(".specs/REQ-2026-001/01_req_spec.md").unlink()
    with pytest.raises(TraceabilityMismatchError, match="does not exist"):
        verify_traceability()


@pytest.mark.requirement("REQ-2026-001-F02")
def test_gate_keeper_validation(mock_state: StateModel) -> None:
    spec_dir = Path(".specs/REQ-2026-001")

    # Missing pair deliverables
    with pytest.raises(GateCheckFailedError, match="Missing mandatory pair deliverable"):
        validate_gate(GateId.GATE1_SPEC)

    spec_dir.joinpath("01_req_spec.md").touch()
    spec_dir.joinpath("01_acceptance_tests.feature").touch()

    # Create missing review dir and valid review
    review_dir = spec_dir / "reviews"
    review_dir.mkdir()
    review_data: dict[str, object] = {
        "gate_id": "GATE1_SPEC",
        "requirement_id": "REQ-2026-001",
        "reviewer_persona": "LEGAL",
        "status": "APPROVED",
        "design_flaws": [],
        "test_design_flaws": [],
        "accepted_tradeoffs": [],
        "reviewed_at": datetime.now(UTC).isoformat(),
    }
    review_dir.joinpath("review.json").write_text(json.dumps(review_data))

    # Should pass gate 1
    validate_gate(GateId.GATE1_SPEC)

    from jtc_gov.services.state_engine import read_state

    new_state = read_state()
    assert new_state.requirements["REQ-2026-001"].current_gate == GateId.GATE2_SYSTEM

    # test gate mismatch error
    with pytest.raises(GateCheckFailedError, match="current gate is GATE2_SYSTEM"):
        validate_gate(GateId.GATE1_SPEC)


@pytest.mark.requirement("REQ-2026-001-F02")
def test_gate_keeper_gate4_human_signoff(mock_state: StateModel) -> None:
    from jtc_gov.services.state_engine import read_state, write_state

    state = read_state()
    req = state.requirements["REQ-2026-001"]
    # We can't update directly (frozen), so update dict
    req_dict = req.model_dump()
    req_dict["current_gate"] = GateId.GATE4_DETAIL
    state_dict = state.model_dump()
    state_dict["requirements"]["REQ-2026-001"] = req_dict
    write_state(StateModel.model_validate(state_dict))

    spec_dir = Path(".specs/REQ-2026-001")
    spec_dir.joinpath("04_detail_design.md").touch()

    Path("tests/test_x.py").touch()

    # Missing decision
    with pytest.raises(GateCheckFailedError, match=r"Missing 05_decision\.md"):
        validate_gate(GateId.GATE4_DETAIL)

    decision = spec_dir / "05_decision.md"
    decision.write_text("No signoff here")

    with pytest.raises(GateCheckFailedError, match="Missing 'HUMAN_SIGN_OFF: APPROVED'"):
        validate_gate(GateId.GATE4_DETAIL)

    decision.write_text("HUMAN_SIGN_OFF: APPROVED by user")
    validate_gate(GateId.GATE4_DETAIL)

    new_state = read_state()
    assert new_state.requirements["REQ-2026-001"].current_gate == GateId.GATE5_IMPL

    # Gate 5 completion test
    Path("src").mkdir()
    Path("src/something.py").touch()
    validate_gate(GateId.GATE5_IMPL)
    assert read_state().requirements["REQ-2026-001"].status == RequirementStatus.COMPLETED


@pytest.mark.requirement("REQ-2026-001-F05")
def test_escalator(mock_state: StateModel) -> None:
    from jtc_gov.services.state_engine import read_state, write_state

    state = read_state()
    req_dict = state.requirements["REQ-2026-001"].model_dump()
    req_dict["current_gate"] = GateId.GATE4_DETAIL
    req_dict["completed_gates"] = [GateId.GATE1_SPEC, GateId.GATE2_SYSTEM, GateId.GATE3_INTEGRATION]
    state_dict = state.model_dump()
    state_dict["requirements"]["REQ-2026-001"] = req_dict
    write_state(StateModel.model_validate(state_dict))

    escalate(to_gate=2, reason="API change")

    new_state = read_state()
    assert new_state.requirements["REQ-2026-001"].current_gate == GateId.GATE2_SYSTEM
    assert new_state.requirements["REQ-2026-001"].status == RequirementStatus.ROLLBACK
    assert new_state.requirements["REQ-2026-001"].completed_gates == [GateId.GATE1_SPEC]

    # Record created
    records = list(Path(".specs/REQ-2026-001/escalations").glob("ESC-*.json"))
    assert len(records) == 1

    # invalid gate mapping
    with pytest.raises(ValueError, match="Invalid target gate"):
        escalate(10, "bad")

    # invalid target (must be previous)
    with pytest.raises(ValueError, match="must be to a previous gate"):
        escalate(3, "bad")


@pytest.mark.requirement("REQ-2026-001-F02")
def test_get_unlocked_paths_for_gate() -> None:
    paths = get_unlocked_paths_for_gate(GateId.GATE3_INTEGRATION, "REQ-2026-001")
    assert ".specs/REQ-2026-001/03_*" in paths
    assert "src/*" not in paths
