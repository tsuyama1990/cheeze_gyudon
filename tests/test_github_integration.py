"""Tests for GitHub Integrations."""

import json
import os
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from jtc_gov.cli import main
from jtc_gov.domain.exceptions import TraceabilityMismatchError
from jtc_gov.integrations.github.action_runner import run_action
from jtc_gov.integrations.github.pr_formatter import format_audit_comment
from jtc_gov.integrations.github.summary_generator import generate_pr_summary


@pytest.fixture
def mock_review_json(tmp_path: Path) -> Path:
    """Fixture to provide a mock gate_review.json."""
    data = {
        "gate": "GATE_4_DETAIL",
        "persona": "Security",
        "status": "REJECTED",
        "fatal_flaws": [
            {
                "id": "F1",
                "severity": "HIGH",
                "description": "SQL injection",
                "action_required": "Use ORM",
            }
        ],
        "accepted_tradeoffs": ["Performance hit for security"],
    }
    file_path = tmp_path / "gate_review.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")
    return file_path


@pytest.fixture
def mock_decision_json(tmp_path: Path) -> Path:
    """Fixture to provide a mock 05_decision.md/json."""
    data = {
        "selected_option": "KISS",
        "rationale": "Keep it simple",
        "review_persona_consensus": {"Security": "APPROVED", "Architecture": "REJECTED"},
        "pending_human_approvals": ["tomoyuki"],
    }
    file_path = tmp_path / "05_decision.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")
    return file_path


@pytest.fixture
def mock_feature_file(tmp_path: Path) -> Path:
    """Fixture to provide a mock feature file."""
    content = (
        "Feature: AI Governance\n"
        "  Scenario: Blocking invalid code\n"
        "    Given state is GATE 1\n"
        "    When agent edits src/\n"
        "    Then tool is blocked\n"
        "    And error is returned\n"
    )
    file_path = tmp_path / "01_acceptance.feature"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.mark.requirement("REQ-2026-003-F01")
def test_format_audit_comment(mock_review_json: Path) -> None:
    """Test format_audit_comment."""
    result = format_audit_comment(str(mock_review_json))
    assert "Governance Audit Report - GATE_4_DETAIL" in result
    assert "**REJECTED**" in result
    assert "SQL injection" in result
    assert "Performance hit for security" in result


@pytest.mark.requirement("REQ-2026-003-F01")
def test_format_audit_comment_missing() -> None:
    """Test format_audit_comment with missing file."""
    result = format_audit_comment("nonexistent.json")
    assert "Audit Deliverable Not Found" in result


@pytest.mark.requirement("REQ-2026-003-F01")
def test_format_audit_comment_invalid_json(tmp_path: Path) -> None:
    """Test format_audit_comment with invalid JSON."""
    file_path = tmp_path / "bad.json"
    file_path.write_text("not json", encoding="utf-8")
    result = format_audit_comment(str(file_path))
    assert "Audit Deliverable Parse Error" in result


@pytest.mark.requirement("REQ-2026-003-F01")
def test_format_audit_comment_no_flaws_no_tradeoffs(tmp_path: Path) -> None:
    """Test format_audit_comment with empty flaws and tradeoffs."""
    data = {
        "gate": "GATE_3",
        "persona": "QA",
        "status": "APPROVED",
        "fatal_flaws": [],
        "accepted_tradeoffs": [],
    }
    file_path = tmp_path / "good.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")
    result = format_audit_comment(str(file_path))
    assert "No Fatal Flaws Detected" in result
    assert "Accepted Trade-offs" not in result


@pytest.mark.requirement("REQ-2026-003-F01")
def test_generate_pr_summary(mock_decision_json: Path, mock_feature_file: Path) -> None:
    """Test generate_pr_summary."""
    result = generate_pr_summary(str(mock_decision_json), str(mock_feature_file))
    assert "Tri-Polar Option Decision" in result
    assert "KISS" in result
    assert "Keep it simple" in result
    assert "✅ Security" in result
    assert "❌ Architecture" in result
    assert "[ ] @tomoyuki" in result
    assert "Feature: AI Governance" in result
    assert "Scenario: Blocking invalid code" in result


@pytest.mark.requirement("REQ-2026-003-F02")
def test_cli_format_pr_comment(mock_review_json: Path) -> None:
    """Test format-pr-comment CLI command."""
    runner = CliRunner()
    result = runner.invoke(main, ["format-pr-comment", "--review-file", str(mock_review_json)])
    assert result.exit_code == 0
    assert "Governance Audit Report" in result.output


@pytest.mark.requirement("REQ-2026-003-F02")
def test_cli_format_pr_summary(mock_decision_json: Path, mock_feature_file: Path) -> None:
    """Test format-pr-summary CLI command."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "format-pr-summary",
            "--decision-file",
            str(mock_decision_json),
            "--feature-file",
            str(mock_feature_file),
        ],
    )
    assert result.exit_code == 0
    assert "Tri-Polar Option Decision" in result.output


@pytest.mark.requirement("REQ-2026-003-F02")
def test_cli_ci_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    """ci-verify passes when traceability holds and fails when it does not."""
    runner = CliRunner()
    monkeypatch.setattr("jtc_gov.cli.verify_traceability", lambda: None)
    result = runner.invoke(main, ["ci-verify"])
    assert result.exit_code == 0
    assert "Running CI Verification..." in result.output
    assert "Traceability check passed." in result.output

    def mismatch() -> None:
        msg = "mismatch"
        raise TraceabilityMismatchError(msg)

    monkeypatch.setattr("jtc_gov.cli.verify_traceability", mismatch)
    assert runner.invoke(main, ["ci-verify"]).exit_code == 1


@pytest.mark.requirement("REQ-2026-003-F03")
@mock.patch.dict(os.environ, {}, clear=True)
def test_run_action_no_event() -> None:
    """Test run_action when GITHUB_EVENT_PATH is not set."""
    assert run_action() == 1


@pytest.mark.requirement("REQ-2026-003-F01")
def test_generate_pr_summary_missing_files() -> None:
    """Test generate_pr_summary with missing files."""
    result = generate_pr_summary("nonexistent_decision.json", "nonexistent_feature.feature")
    assert "No 05_decision.md/json provided" in result


@pytest.mark.requirement("REQ-2026-003-F01")
def test_generate_pr_summary_invalid_json(tmp_path: Path, mock_feature_file: Path) -> None:
    """Test generate_pr_summary with invalid decision JSON."""
    bad_json = tmp_path / "bad_decision.json"
    bad_json.write_text("not json", encoding="utf-8")
    result = generate_pr_summary(str(bad_json), str(mock_feature_file))
    assert "Failed to parse decision JSON" in result


@pytest.mark.requirement("REQ-2026-003-F01")
def test_generate_pr_summary_empty_consensus(tmp_path: Path, mock_feature_file: Path) -> None:
    """Test generate_pr_summary with empty consensus and approvals."""
    data = {"selected_option": "KISS"}
    decision = tmp_path / "empty_decision.json"
    decision.write_text(json.dumps(data), encoding="utf-8")
    result = generate_pr_summary(str(decision), str(mock_feature_file))
    assert "Tri-Polar Option Decision" in result
    assert "Review Persona Consensus" not in result
    assert "Pending Human Approvals" not in result


@pytest.mark.requirement("REQ-2026-003-F03")
def test_run_action_with_event(tmp_path: Path) -> None:
    """Test run_action with valid PR event path."""
    event_data = {
        "pull_request": {
            "head": {"ref": "feat/gate3-update"},
            "labels": [{"name": "bug"}, {"name": "gate:4"}],
        }
    }
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps(event_data), encoding="utf-8")

    with mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(event_file)}):
        result = run_action()
        assert result == 0


@pytest.mark.requirement("REQ-2026-003-F03")
def test_run_action_invalid_path() -> None:
    """Test run_action with nonexistent path."""
    with mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": "missing.json"}):
        assert run_action() == 1


@pytest.mark.requirement("REQ-2026-003-F03")
def test_run_action_invalid_json(tmp_path: Path) -> None:
    """Test run_action with invalid JSON."""
    event_file = tmp_path / "bad.json"
    event_file.write_text("not json", encoding="utf-8")
    with mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(event_file)}):
        assert run_action() == 1


@pytest.mark.requirement("REQ-2026-003-F03")
def test_run_action_not_pull_request(tmp_path: Path) -> None:
    """Test run_action with no pull_request key."""
    event_file = tmp_path / "push.json"
    event_file.write_text(json.dumps({"push": {}}), encoding="utf-8")
    with mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(event_file)}):
        assert run_action() == 0


@pytest.mark.requirement("REQ-2026-003-F03")
def test_run_action_branches(tmp_path: Path) -> None:
    """Test run_action parsing branches."""
    for branch, _expected in [("gate1", "1"), ("gate2", "2"), ("gate3", "3"), ("feat/x", "5")]:
        event_data = {
            "pull_request": {
                "head": {"ref": branch},
            }
        }
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(event_data), encoding="utf-8")
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(event_file)}):
            assert run_action() == 0
