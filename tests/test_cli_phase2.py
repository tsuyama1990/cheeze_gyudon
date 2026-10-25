"""Tests for Phase 2 CLI subcommands."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from jtc_gov.cli import main
from jtc_gov.domain.review_models import GateReview


@pytest.fixture()
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
    ]


@pytest.mark.requirement("REQ-2026-002-F0x")
@patch("jtc_gov.cli.run_redteam_gate", create=True)
def test_redteam_success(mock_run_redteam: MagicMock, mock_reviews: list[GateReview]) -> None:
    mock_run_redteam.return_value = mock_reviews
    runner = CliRunner()
    result = runner.invoke(main, ["redteam", "--gate", "gate_1", "--preset", "SOLO_TOOL"])
    assert result.exit_code == 0
    assert "Redteam complete. Generated 1 reviews for gate_1." in result.output
    mock_run_redteam.assert_called_once_with(gate_id="gate_1", preset="SOLO_TOOL")


@pytest.mark.requirement("REQ-2026-002-F0x")
@patch("jtc_gov.cli.run_redteam_gate", create=True)
def test_redteam_failure(mock_run_redteam: MagicMock) -> None:
    mock_run_redteam.side_effect = ValueError("Test error")
    runner = CliRunner()
    result = runner.invoke(main, ["redteam", "--gate", "gate_1"])
    assert result.exit_code == 1
    assert "Failed to run redteam: Test error" in result.output


@pytest.mark.requirement("REQ-2026-002-F0x")
@patch("jtc_gov.cli.draft_decision", create=True)
def test_draft_decision_success(mock_draft_decision: MagicMock) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["draft-decision", "--req", "REQ-TEST"])
    assert result.exit_code == 0
    assert "Decision drafted successfully for REQ-TEST." in result.output
    mock_draft_decision.assert_called_once_with(requirement_id="REQ-TEST")


@pytest.mark.requirement("REQ-2026-002-F0x")
@patch("jtc_gov.cli.draft_decision", create=True)
def test_draft_decision_failure(mock_draft_decision: MagicMock) -> None:
    mock_draft_decision.side_effect = Exception("Test exception")
    runner = CliRunner()
    result = runner.invoke(main, ["draft-decision", "--req", "REQ-TEST"])
    assert result.exit_code == 1
    assert "Failed to draft decision: Test exception" in result.output


@pytest.mark.requirement("REQ-2026-002-F0x")
@patch("jtc_gov.cli.load_reviews", create=True)
def test_review_status_no_reviews(mock_load_reviews: MagicMock) -> None:
    mock_load_reviews.return_value = []
    runner = CliRunner()
    result = runner.invoke(main, ["review-status", "--gate", "gate_1"])
    assert result.exit_code == 0
    assert "No reviews found for gate: gate_1" in result.output


@pytest.mark.requirement("REQ-2026-002-F0x")
@patch("jtc_gov.cli.load_reviews", create=True)
def test_review_status_with_reviews(
    mock_load_reviews: MagicMock, mock_reviews: list[GateReview]
) -> None:
    mock_load_reviews.return_value = mock_reviews
    runner = CliRunner()
    result = runner.invoke(main, ["review-status", "--gate", "gate_1"])
    assert result.exit_code == 0
    assert "Gate gate_1 Review Status:" in result.output
    assert "Total Reviews: 1" in result.output
    assert "Approved: 0 / 1" in result.output
    assert "Total Flaws Identified: 1" in result.output


@pytest.mark.requirement("REQ-2026-002-F0x")
@patch("jtc_gov.cli.load_reviews", create=True)
def test_review_status_with_state_json(
    mock_load_reviews: MagicMock,
    mock_reviews: list[GateReview],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_load_reviews.return_value = mock_reviews

    # Create fake state json
    specs_dir = tmp_path / ".specs"
    specs_dir.mkdir()
    state_file = specs_dir / "state.json"
    state_file.write_text(json.dumps({"active_requirement_id": "REQ-STATE"}))

    class MockPath:
        def __init__(self: "MockPath", _p: str | Path | object) -> None:
            pass

        def exists(self: "MockPath") -> bool:
            return True

        def read_text(self: "MockPath", encoding: str | None = None) -> str:
            _ = encoding
            return json.dumps({"active_requirement_id": "REQ-STATE"})

    monkeypatch.setattr("jtc_gov.cli.Path", MockPath)

    runner = CliRunner()
    result = runner.invoke(main, ["review-status", "--gate", "gate_1"])
    assert result.exit_code == 0
    mock_load_reviews.assert_called_once_with(requirement_id="REQ-STATE")


@pytest.mark.requirement("REQ-2026-002-F0x")
@patch("jtc_gov.cli.load_reviews", create=True)
def test_review_status_with_invalid_state_json(
    mock_load_reviews: MagicMock,
    mock_reviews: list[GateReview],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_load_reviews.return_value = mock_reviews

    class MockPath:
        def __init__(self: "MockPath", _p: str | Path | object) -> None:
            pass

        def exists(self: "MockPath") -> bool:
            return True

        def read_text(self: "MockPath", encoding: str | None = None) -> str:
            _ = encoding
            return "invalid json"

    monkeypatch.setattr("jtc_gov.cli.Path", MockPath)

    runner = CliRunner()
    result = runner.invoke(main, ["review-status", "--gate", "gate_1"])
    assert result.exit_code == 0
    mock_load_reviews.assert_called_once_with(requirement_id="REQ-000")
