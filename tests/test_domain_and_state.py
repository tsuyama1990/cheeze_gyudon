from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from jtc_gov.domain.exceptions import StateCorruptedError
from jtc_gov.domain.legacy_models import (
    GateId,
    GateReviewDeliverable,
    RequirementItem,
    RequirementStatus,
    StateModel,
)
from jtc_gov.services.state_engine import is_path_unlocked, read_state, write_state


@pytest.mark.requirement("REQ-2026-001-F01")
def test_requirement_item_validation() -> None:
    req = RequirementItem(
        title="Test Req",
        current_gate=GateId.GATE1_SPEC,
        status=RequirementStatus.IN_PROGRESS,
        unlocked_paths=[".specs/*"],
        completed_gates=[],
    )
    assert req.title == "Test Req"
    assert req.current_gate == GateId.GATE1_SPEC

    with pytest.raises(ValidationError):
        # frozen model modification
        req.title = "New Title"


@pytest.mark.requirement("REQ-2026-001-F01")
def test_state_model_validation() -> None:
    req = RequirementItem(
        title="Test", current_gate=GateId.GATE1_SPEC, status=RequirementStatus.IN_PROGRESS
    )
    state = StateModel(active_requirement_id="REQ-0000", requirements={"REQ-0000": req})
    assert state.active_requirement_id == "REQ-0000"


@pytest.mark.requirement("REQ-2026-001-F01")
def test_gate_review_deliverable_validation() -> None:
    # Valid
    GateReviewDeliverable(
        gate_id=GateId.GATE1_SPEC,
        requirement_id="REQ-2026-001",
        reviewer_persona="LEGAL",
        status="APPROVED",
        design_flaws=[],
        test_design_flaws=[],
        accepted_tradeoffs=[],
        reviewed_at=datetime.now(UTC),
    )

    with pytest.raises(ValidationError):
        # Too many design flaws
        GateReviewDeliverable(
            gate_id=GateId.GATE1_SPEC,
            requirement_id="REQ-2026-001",
            reviewer_persona="LEGAL",
            status="APPROVED",
            design_flaws=["1", "2", "3"],
            test_design_flaws=[],
            accepted_tradeoffs=[],
            reviewed_at=datetime.now(UTC),
        )


@pytest.mark.requirement("REQ-2026-001-F01")
def test_is_path_unlocked() -> None:
    unlocked = [".specs/REQ-2026-001/01_*", "src/*"]
    assert is_path_unlocked(".specs/REQ-2026-001/01_req_spec.md", unlocked)
    assert is_path_unlocked("src/service.py", unlocked)
    assert not is_path_unlocked("tests/test_service.py", unlocked)


@pytest.mark.requirement("REQ-2026-001-F01")
def test_is_path_unlocked_absolute_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = str(tmp_path / "src" / "a.py")
    assert is_path_unlocked(target, ["src/*"]) is True


@pytest.mark.requirement("REQ-2026-001-F01")
def test_is_path_unlocked_absolute_locked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = str(tmp_path / "tests" / "a.py")
    assert is_path_unlocked(target, ["src/*"]) is False


@pytest.mark.requirement("REQ-2026-001-F01")
def test_is_path_unlocked_outside_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    outside = str(tmp_path.parent / "outside.py")
    assert is_path_unlocked(outside, ["*"]) is False


@pytest.mark.requirement("REQ-2026-001-F01")
def test_is_path_unlocked_traversal_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert is_path_unlocked("../outside.py", ["*"]) is False


@pytest.mark.requirement("REQ-2026-001-F01")
def test_read_write_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"

    # Mock get_state_path to use temp file
    monkeypatch.setattr("jtc_gov.services.state_engine.get_state_path", lambda: state_file)

    # Reading missing file raises error
    with pytest.raises(StateCorruptedError):
        read_state()

    req = RequirementItem(
        title="Test", current_gate=GateId.GATE1_SPEC, status=RequirementStatus.IN_PROGRESS
    )
    state = StateModel(active_requirement_id="REQ-0000", requirements={"REQ-0000": req})

    # Write and read back
    write_state(state)
    assert state_file.exists()

    loaded_state = read_state()
    assert loaded_state.active_requirement_id == "REQ-0000"
    assert "REQ-0000" in loaded_state.requirements

    # Write failure error handling
    def mock_replace(self: Path, target: str | Path) -> Path:
        msg = "Mock write error"
        raise StateCorruptedError(msg)

    monkeypatch.setattr(Path, "replace", mock_replace)
    with pytest.raises(StateCorruptedError):
        write_state(state)

    # Read failure error handling
    state_file.write_text("invalid json")
    with pytest.raises(StateCorruptedError):
        read_state()
