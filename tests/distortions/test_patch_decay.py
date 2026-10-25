# ruff: noqa: S603, S607
"""Test patch decay interception."""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.requirement("REQ-2026-004-F02")
def test_patch_decay_complexity_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates agent introducing high-complexity spaghetti (McCabe > 10) -> Rejected by Ruff."""
    monkeypatch.chdir(tmp_path)

    # Need a pyproject.toml configuring ruff mccabe limit
    pyproject = Path("pyproject.toml")
    pyproject.write_text("[tool.ruff.lint.mccabe]\nmax-complexity = 10\n", encoding="utf-8")

    src_file = Path("bad_code.py")

    # Create a function with cyclomatic complexity > 10
    complex_code = "def spaghetti():\n"
    for i in range(12):
        complex_code += f"    if {i} == 1:\n        pass\n"

    src_file.write_text(complex_code, encoding="utf-8")

    # Run ruff check on the file
    # Ensure ruff checks for complexity (C901 in ruff corresponds to mccabe)
    result = subprocess.run(
        ["uv", "run", "ruff", "check", "--select", "C90", str(src_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    # Must fail
    assert result.returncode != 0
    assert "C901" in result.stdout
    assert "is too complex" in result.stdout
