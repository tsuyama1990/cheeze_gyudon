import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jtc_gov.domain.review_models import GateReview
from jtc_gov.services.decision_engine import draft_decision, generate_tripolar_matrix, load_reviews


@pytest.fixture
def mock_reviews() -> list[GateReview]:
    return [
        GateReview(
            gate_id="gate_1",
            requirement_id="REQ-TEST",
            reviewer_persona="ux_critic",
            status="REJECTED",
            design_flaws=["flaw1"],
            test_design_flaws=[],
            reviewed_at=datetime.now(UTC).isoformat(),
        ),
        GateReview(
            gate_id="gate_1",
            requirement_id="REQ-TEST",
            reviewer_persona="lazy_senior_dev",
            status="APPROVED",
            design_flaws=[],
            test_design_flaws=["flaw2"],
            reviewed_at=datetime.now(UTC).isoformat(),
        ),
    ]


@pytest.mark.requirement("REQ-2026-002-F0x")
def test_tripolar_matrix_generation(mock_reviews: list[GateReview]) -> None:
    """Tests Tri-Polar matrix generation and human sign-off validation."""
    content = generate_tripolar_matrix("REQ-TEST", mock_reviews)

    assert "Decision Record for REQ-TEST" in content
    assert "Total flaws identified across reviews: 2" in content
    assert "| Option 1 | KISS / Minimum Cost | Low |" in content
    assert "HUMAN_SIGN_OFF: APPROVED by @username at " in content


@pytest.mark.requirement("REQ-2026-002-F0x")
def test_draft_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_reviews: list[GateReview]
) -> None:
    """Tests drafting decision writing to file."""
    monkeypatch.setattr("jtc_gov.services.decision_engine.SPECS_DIR", tmp_path)

    # Mock load_reviews to return our fixture
    def mock_load(_req_id: str) -> list[GateReview]:
        return mock_reviews

    monkeypatch.setattr("jtc_gov.services.decision_engine.load_reviews", mock_load)

    draft_decision("REQ-TEST")

    decision_file = tmp_path / "REQ-TEST" / "05_decision.md"
    assert decision_file.exists()

    content = decision_file.read_text(encoding="utf-8")
    assert "Decision Record for REQ-TEST" in content


@pytest.mark.requirement("REQ-2026-002-F0x")
def test_load_reviews(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_reviews: list[GateReview]
) -> None:
    """Tests loading reviews."""
    monkeypatch.setattr("jtc_gov.services.decision_engine.SPECS_DIR", tmp_path)

    req_id = "REQ-TEST-LOAD"

    # Empty dir
    assert load_reviews(req_id) == []

    reviews_dir = tmp_path / req_id / "reviews"
    reviews_dir.mkdir(parents=True)

    # Valid file
    file1 = reviews_dir / "gate_1_ux.json"
    file1.write_text(mock_reviews[0].model_dump_json(), encoding="utf-8")

    # Invalid file
    file2 = reviews_dir / "invalid.json"
    file2.write_text("invalid json", encoding="utf-8")

    # Missing required fields
    file3 = reviews_dir / "bad_schema.json"
    file3.write_text(json.dumps({"gate_id": "gate_1"}), encoding="utf-8")

    loaded = load_reviews(req_id)
    assert len(loaded) == 1
    assert loaded[0].reviewer_persona == "ux_critic"
