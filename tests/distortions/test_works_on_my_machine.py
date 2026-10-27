# ruff: noqa: S603, S607
"""Test works on my machine interception."""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.requirement("REQ-2026-010-F04")
def test_unpinned_dependency_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates agent introducing unpinned external dependencies without uv.lock -> Rejected."""
    monkeypatch.chdir(tmp_path)

    # Attempt to install a package dynamically without locking
    # In a real environment, uv run would fail if the package isn't in pyproject.toml / uv.lock

    # We will simulate a check that verifies uv pip install is not used directly
    # instead of uv sync / locked deps, or simply test that uv run fails without it.

    script = Path("run_unpinned.py")
    script.write_text("import requests\nprint(requests.__version__)\n", encoding="utf-8")

    result = subprocess.run(
        ["uv", "run", "python", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )

    # uv run in an isolated environment without requests should fail
    assert result.returncode != 0
    assert "ModuleNotFoundError" in result.stderr or "No module named 'requests'" in result.stderr
