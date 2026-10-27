# ruff: noqa: S603, S607
"""Test zombie code interception."""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.requirement("REQ-2026-010-F04")
def test_zombie_code_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates agent creating unused helper functions -> Blocked by Vulture."""
    monkeypatch.chdir(tmp_path)

    src_file = Path("bloat.py")

    # Create an unused helper function
    src_file.write_text("def _unused_helper() -> int:\n    return 42\n", encoding="utf-8")

    result = subprocess.run(
        ["uv", "run", "vulture", str(src_file), "--min-confidence", "60"],
        capture_output=True,
        text=True,
        check=False,
    )

    # Vulture should exit with a non-zero code when dead code is found
    assert result.returncode != 0
    assert "unused function '_unused_helper'" in result.stdout
