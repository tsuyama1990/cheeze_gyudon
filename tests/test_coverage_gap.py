import contextlib

# ruff: noqa: E501, PLR0915, PLC0415, ARG005, ARG001
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

    result = runner.invoke(main, ["approve-decision"])
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
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"current_gate": "GATE3_SPEC"}}}'
    )
    result = runner.invoke(main, ["gate-check", "--gate", "2"])
    assert result.exit_code == 1

    result = runner.invoke(main, ["approve-decision"])
    assert result.exit_code == 1

    # Extract file coverage
    result = runner.invoke(main, ["verify-tool", "--input", '{"invalid": true}'])

    result = runner.invoke(main, ["verify-tool", "--input", '{"file_path": ["invalid"]}'])

    # Status missing
    result = runner.invoke(main, ["status"])

    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"current_gate": "GATE3_SPEC"}}}'
    )
    result = runner.invoke(main, ["status"])


def test_is_path_unlocked() -> None:
    from jtc_gov.cli import is_path_unlocked

    assert is_path_unlocked("dir/file.txt", ["dir/*"])
    assert not is_path_unlocked("dir/file.txt", ["other/*"])
    assert is_path_unlocked("./dir/file.txt", ["dir/*"])
    assert is_path_unlocked("dir\\file.txt", ["dir/*"])


def test_extract_target_file() -> None:
    from jtc_gov.cli import extract_target_file

    assert extract_target_file(None, "file.txt") == "file.txt"
    assert extract_target_file(None, None) is None
    assert extract_target_file('{"file_path": "test.txt"}', None) == "test.txt"
    assert extract_target_file('{"invalid json', None) is None


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
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"current_gate": "GATE1_SPEC", "unlocked_paths": ["test.py"]}}}'
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
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"current_gate": "GATE1_SPEC"}}}'
    )
    result = runner.invoke(main, ["gate-check", "--gate", "1"])
    assert result.exit_code == 0

    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"current_gate": "GATE4_SPEC"}}}'
    )
    result = runner.invoke(main, ["gate-check", "--gate", "4"])
    assert result.exit_code == 0

    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"current_gate": "GATE5_IMPLEMENTATION"}}}'
    )
    result = runner.invoke(main, ["gate-check", "--gate", "5"])
    assert result.exit_code == 0

    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"current_gate": "GATE4.5_DECISION"}}}'
    )
    result = runner.invoke(main, ["approve-decision"])
    assert result.exit_code == 0

    # Catch OS/JSON decode errors in process state
    # using monkeypatch
    def mock_loads(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        msg = "msg"
        raise json.JSONDecodeError(msg, "doc", 0)

    import json

    monkeypatch.setattr(json, "loads", mock_loads)
    result = runner.invoke(main, ["gate-check", "--gate", "1"])
    assert result.exit_code == 1

    result = runner.invoke(main, ["approve-decision"])
    assert result.exit_code == 1

    result = runner.invoke(main, ["escalate", "--gate", "1", "--reason", "test"])
    assert result.exit_code == 1

    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0

    monkeypatch.undo()  # Unmock json
    Path(".specs/state.json").write_text(
        '{"active_requirement_id": "REQ-1", "requirements": {"REQ-1": {"current_gate": "GATE5_IMPLEMENTATION"}}}'
    )
    result = runner.invoke(main, ["escalate", "--gate", "1", "--reason", "test"])
    assert result.exit_code == 0
