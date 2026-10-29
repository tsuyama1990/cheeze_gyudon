import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).parents[2]
STEPS = ("ruff", "mypy", "vulture", "pytest", "diff-cover", "gov", "pre-commit")
FAKE_UV = """#!/usr/bin/env bash
# records "<tool> <args>" and fails when the tool is FAIL_TOOL; `uv run python -c` runs for real
if [ "$1" = "run" ] && [ "$2" = "python" ]; then shift 2; exec python3 "$@"; fi
shift
echo "$@" >> "$CALLS"
[ "$1" = "$FAIL_TOOL" ] && exit 1
exit 0
"""


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    shutil.copy(PROJECT / "scripts" / "gate.sh", tmp_path / "scripts" / "gate.sh")
    (tmp_path / "pyproject.toml").write_text("[tool.coverage.report]\nfail_under = 77\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(FAKE_UV)
    uv.chmod(uv.stat().st_mode | stat.S_IEXEC)
    return tmp_path


def run_gate(sandbox: Path, **env: str) -> tuple[int, list[str]]:
    calls = sandbox / "calls.log"
    calls.write_text("")
    environment = {
        **{k: v for k, v in os.environ.items() if k != "GATE_BASE"},
        "PATH": f"{sandbox / 'bin'}:{os.environ['PATH']}",
        "CALLS": str(calls),
        **env,
    }
    done = subprocess.run(
        ["bash", "scripts/gate.sh"],  # noqa: S607
        cwd=sandbox,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, calls.read_text().splitlines()


@pytest.mark.requirement("REQ-2026-010-F09")
@pytest.mark.spec("L2-I39")
def test_gate_runs_every_step_in_order(sandbox: Path) -> None:
    code, calls = run_gate(sandbox)
    assert code == 0
    assert [c.split()[0] for c in calls] == [
        "ruff",
        "ruff",
        "mypy",
        "vulture",
        "pytest",
        "diff-cover",
        "gov",
        "pre-commit",
    ]


@pytest.mark.requirement("REQ-2026-010-F09")
@pytest.mark.spec("L2-I39")
@pytest.mark.parametrize("failing", STEPS)
def test_gate_stops_at_the_first_failing_step(sandbox: Path, failing: str) -> None:
    code, calls = run_gate(sandbox, FAIL_TOOL=failing)
    assert code != 0
    assert calls[-1].split()[0] == failing
    assert STEPS.index(calls[-1].split()[0]) == STEPS.index(failing)


@pytest.mark.requirement("REQ-2026-010-F09")
@pytest.mark.spec("L2-I40")
def test_gate_base_reaches_diff_cover_and_gov_check(sandbox: Path) -> None:
    _, calls = run_gate(sandbox, GATE_BASE="origin/release")
    diff_cover = next(c for c in calls if c.startswith("diff-cover"))
    gov = next(c for c in calls if c.startswith("gov"))
    assert "--compare-branch=origin/release" in diff_cover
    assert "origin/release" in gov
    _, default_calls = run_gate(sandbox)
    assert "origin/main" in next(c for c in default_calls if c.startswith("gov"))


@pytest.mark.requirement("REQ-2026-010-F04")
@pytest.mark.spec("L2-I41")
def test_gate_passes_the_configured_threshold_and_fails_without_one(sandbox: Path) -> None:
    _, calls = run_gate(sandbox)
    assert "--fail-under=77" in next(c for c in calls if c.startswith("diff-cover"))
    (sandbox / "pyproject.toml").write_text("[tool.coverage.report]\n")
    code, calls = run_gate(sandbox)
    assert code != 0
    assert not any(c.startswith("diff-cover") for c in calls)
