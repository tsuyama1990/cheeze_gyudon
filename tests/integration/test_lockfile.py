import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).parents[2]


@pytest.mark.requirement("REQ-2026-010-F04")
def test_lockfile_matches_pyproject() -> None:
    """A dependency added to pyproject.toml without updating uv.lock must fail here."""
    done = subprocess.run(
        ["uv", "lock", "--check", "--offline"],  # noqa: S607
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
