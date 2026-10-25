"""Test mock drift interception."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.cli import trace_check

REQ_ID = "REQ-2026-123"


def _setup_project(root: Path, spec_reqs: list[str], test_reqs: list[str]) -> None:
    (root / ".specs" / REQ_ID).mkdir(parents=True)
    (root / ".specs" / "state.json").write_text(
        json.dumps(
            {
                "active_requirement_id": REQ_ID,
                "requirements": {
                    REQ_ID: {
                        "title": "t",
                        "current_gate": "GATE5_IMPL",
                        "status": "IN_PROGRESS",
                        "unlocked_paths": [],
                        "completed_gates": [],
                    }
                },
            }
        )
    )
    spec = "\n".join(f"- [{r}] requirement" for r in spec_reqs)
    (root / ".specs" / REQ_ID / "01_req_spec.md").write_text(spec)
    (root / "tests").mkdir()
    body = "".join(
        f'@pytest.mark.requirement("{r}")\ndef test_{i}() -> None: ...\n'
        for i, r in enumerate(test_reqs)
    )
    (root / "tests" / "test_x.py").write_text("import pytest\n" + body)


@pytest.mark.requirement("REQ-2026-004-F04")
def test_mock_drift_trace_check_rejects_phantom_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulates agent adding a test for a requirement absent from the spec -> Rejected."""
    monkeypatch.chdir(tmp_path)
    _setup_project(tmp_path, [f"{REQ_ID}-F01"], [f"{REQ_ID}-F01", f"{REQ_ID}-F99"])

    result = CliRunner().invoke(trace_check)

    assert result.exit_code == 1
    assert f"{REQ_ID}-F99" in result.output


@pytest.mark.requirement("REQ-2026-004-F04")
def test_mock_drift_trace_check_passes_when_aligned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec requirements and test markers match exactly -> Accepted."""
    monkeypatch.chdir(tmp_path)
    _setup_project(tmp_path, [f"{REQ_ID}-F01"], [f"{REQ_ID}-F01"])

    result = CliRunner().invoke(trace_check)

    assert result.exit_code == 0
