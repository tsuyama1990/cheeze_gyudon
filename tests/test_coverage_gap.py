import contextlib

# ruff: noqa: E501, PLR0915, ARG005
import sys
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from jtc_gov.cli import main
from jtc_gov.diagnostics.doctor import run_diagnostics
from jtc_gov.scaffold.initializer import init_project


def test_doctor_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock sys.version_info and shutil.which to hit other branches
    import shutil

    monkeypatch.setattr(sys, "version_info", (3, 10))
    monkeypatch.setattr(shutil, "which", lambda x: None)

    # Mock time.time to test latency >= 50ms and exception
    import time

    calls = [0]

    def fake_time() -> int:
        if calls[0] == 0:
            calls[0] += 1
            return 0
        return 1

    monkeypatch.setattr(time, "time", fake_time)

    # Run diagnostics
    with contextlib.suppress(SystemExit):
        run_diagnostics()

    # Second run for git hooks fail and latency pass
    monkeypatch.setattr(sys, "version_info", (3, 12))
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/uv")

    with contextlib.suppress(SystemExit):
        run_diagnostics()


def test_scaffold_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    init_project(ci="github")
    assert Path(".github/workflows/gate_pipeline.yml").exists()


def test_cli_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # Hit missing state.json blocks
    result = runner.invoke(main, ["gate-check", "--gate", "2"])
    assert result.exit_code == 1

    result = runner.invoke(main, ["escalate", "--gate", "1", "--reason", "test"])
    assert result.exit_code == 1

    Path(".specs").mkdir(exist_ok=True)
    Path(".specs/state.json").write_text("invalid json")

    result = runner.invoke(main, ["gate-check", "--gate", "2"])
    assert result.exit_code == 1

    Path(".specs/state.json").write_text('{"active_requirement_id": ""}')
    result = runner.invoke(main, ["gate-check", "--gate", "2"])
    assert result.exit_code == 1

    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE3_INTEGRATION", "status": "IN_PROGRESS", "unlocked_paths": [], "completed_gates": []}}}'
    )
    result = runner.invoke(main, ["gate-check", "--gate", "2"])
    assert result.exit_code == 1

    # Extract file coverage
    result = runner.invoke(main, ["verify-tool", "--input", '{"invalid": true}'])

    result = runner.invoke(main, ["verify-tool", "--input", '{"file_path": ["invalid"]}'])

    # Status missing
    result = runner.invoke(main, ["status"])

    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE3_INTEGRATION", "status": "IN_PROGRESS", "unlocked_paths": [], "completed_gates": []}}}'
    )
    result = runner.invoke(main, ["status"])


def test_is_path_unlocked() -> None:
    from jtc_gov.services.state_engine import is_path_unlocked

    assert is_path_unlocked("dir/file.txt", ["dir/*"])
    assert not is_path_unlocked("dir/file.txt", ["other/*"])
    assert is_path_unlocked("./dir/file.txt", ["dir/*"])
    assert is_path_unlocked("dir\\file.txt", ["dir/*"])


def test_verify_tool_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # Run verify-tool when no state.json exists
    result = runner.invoke(main, ["verify-tool", "--file", "test.py"])
    assert result.exit_code == 0

    Path(".specs").mkdir(exist_ok=True)
    Path(".specs/state.json").write_text("invalid json")

    result = runner.invoke(main, ["verify-tool", "--file", "test.py"])
    assert result.exit_code == 1

    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE1_SPEC", "status": "IN_PROGRESS", "unlocked_paths": ["test.py"], "completed_gates": []}}}'
    )
    result = runner.invoke(main, ["verify-tool", "--file", "test.py"])
    assert result.exit_code == 0

    result = runner.invoke(main, ["verify-tool", "--file", "invalid.py"])
    assert result.exit_code == 1

    # Missing args
    result = runner.invoke(main, ["verify-tool"])
    assert result.exit_code == 0


def test_cli_coverage_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # Init without CI
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0

    # Doctor missing uv
    import shutil

    monkeypatch.setattr(shutil, "which", lambda x: None)
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 1

    Path(".specs").mkdir(exist_ok=True)

    # Gate checks successful runs (mocked state)
    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE1_SPEC", "status": "IN_PROGRESS", "unlocked_paths": [], "completed_gates": []}}}'
    )
    spec_dir = Path(".specs/REQ-1")
    spec_dir.mkdir()
    (spec_dir / "01_req_spec.md").write_text("spec")
    (spec_dir / "01_acceptance_tests.feature").write_text("feature")
    result = runner.invoke(main, ["gate-check", "--gate", "1"])
    assert result.exit_code == 0

    (spec_dir / "04_detail_design.md").write_text("design")
    (spec_dir / "05_decision.md").write_text("HUMAN_SIGN_OFF: APPROVED")
    Path("tests").mkdir()
    Path("tests/test_x.py").write_text("")
    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE4_DETAIL", "status": "IN_PROGRESS", "unlocked_paths": [], "completed_gates": []}}}'
    )
    result = runner.invoke(main, ["gate-check", "--gate", "4"])
    assert result.exit_code == 0

    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE5_IMPL", "status": "IN_PROGRESS", "unlocked_paths": [], "completed_gates": []}}}'
    )
    result = runner.invoke(main, ["gate-check", "--gate", "5"])
    assert result.exit_code == 0

    # Catch OS/JSON decode errors in process state
    # using monkeypatch
    def mock_loads(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        msg = "msg"
        raise json.JSONDecodeError(msg, "doc", 0)

    import json

    with monkeypatch.context() as patch:
        patch.setattr(json, "loads", mock_loads)
        result = runner.invoke(main, ["gate-check", "--gate", "1"])
        assert result.exit_code == 1

        result = runner.invoke(main, ["escalate", "--gate", "1", "--reason", "test"])
        assert result.exit_code == 1

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 1  # corrupted state is reported, not swallowed

    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"title": "t", "current_gate": "GATE5_IMPL", "status": "IN_PROGRESS", "unlocked_paths": [], "completed_gates": []}}}'
    )
    result = runner.invoke(main, ["escalate", "--gate", "1", "--reason", "test"])
    assert result.exit_code == 0
