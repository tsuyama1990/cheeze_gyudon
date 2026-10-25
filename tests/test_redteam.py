from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from jtc_gov.domain.review_models import GateReview
from jtc_gov.services.redteam_engine import load_persona, run_redteam_gate


@pytest.mark.requirement("REQ-2026-002-F0x")
def test_schema_enforcement_max_flaws() -> None:
    """Validates schema enforcement (rejection of >2 fatal flaws)."""
    with pytest.raises(ValidationError) as exc:
        GateReview(
            gate_id="gate_1",
            requirement_id="REQ-000",
            reviewer_persona="ux_critic",
            status="REJECTED",
            design_flaws=["flaw1", "flaw2", "flaw3"],
            test_design_flaws=[],
            reviewed_at=datetime.now(UTC).isoformat(),
        )
    assert "design_flaws cannot have more than 2 items" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        GateReview(
            gate_id="gate_1",
            requirement_id="REQ-000",
            reviewer_persona="ux_critic",
            status="REJECTED",
            design_flaws=[],
            test_design_flaws=["flaw1", "flaw2", "flaw3"],
            reviewed_at=datetime.now(UTC).isoformat(),
        )
    assert "test_design_flaws cannot have more than 2 items" in str(exc.value)


@pytest.mark.requirement("REQ-2026-002-F0x")
def test_schema_enforcement_missing_fields() -> None:
    """Validates schema enforcement (missing fields)."""
    with pytest.raises(ValidationError):
        GateReview(
            gate_id="gate_1",
            requirement_id="REQ-000",
            # missing reviewer_persona
            status="REJECTED",  # type: ignore[call-arg]
            reviewed_at=datetime.now(UTC).isoformat(),
        )


@pytest.mark.requirement("REQ-2026-002-F0x")
def test_persona_preset_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates persona preset resolution and mock review generation."""
    # Monkeypatch the SPECS_DIR to point to tmp_path to avoid creating files in actual dir
    monkeypatch.setattr("jtc_gov.services.redteam_engine.SPECS_DIR", tmp_path)

    reviews = run_redteam_gate(gate_id="gate_1", preset="SOLO_TOOL", requirement_id="REQ-TEST")

    assert len(reviews) == 3
    personas = [r.reviewer_persona for r in reviews]
    assert "ux_critic" in personas
    assert "lazy_senior_dev" in personas
    assert "finops_sec_lite" in personas

    review_files = list((tmp_path / "REQ-TEST" / "reviews").glob("*.json"))
    assert len(review_files) == 3

    with pytest.raises(ValueError, match="Unknown preset"):
        run_redteam_gate(gate_id="gate_1", preset="INVALID_PRESET")


@pytest.mark.requirement("REQ-2026-002-F0x")
def test_load_persona(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates loading mock personas when real ones missing."""

    # Temporarily point __file__ to tmp_path to fake not finding the file
    class MockPath:
        def __init__(self: "MockPath", _p: str | Path | object) -> None:
            pass

        def exists(self: "MockPath") -> bool:
            return True

        def read_text(self: "MockPath", encoding: str | None = None) -> str:
            _ = encoding
            return "invalid json"

    monkeypatch.setattr("jtc_gov.services.redteam_engine.Path", MockPath)

    # Actually mock exists to return False so it returns the fallback logic
    class MockPath2:
        def __init__(self: "MockPath2", _p: str | Path | object) -> None:
            pass

        @property
        def parent(self: "MockPath2") -> "MockPath2":
            return MockPath2(self)

        def __truediv__(self: "MockPath2", other: str | object) -> "MockPath2":
            return MockPath2(self)

        def exists(self: "MockPath2") -> bool:
            return False

    monkeypatch.setattr("jtc_gov.services.redteam_engine.Path", MockPath2)
    result = load_persona("missing_persona")
    assert result == "Mock persona for missing_persona"
