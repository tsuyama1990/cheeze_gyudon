import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.integration.test_repo_git import commit, root  # noqa: F401

BIN = Path(sys.executable).parent
THRESHOLD = 90
PYPROJECT = f"""[tool.pytest.ini_options]
pythonpath = ["src"]
addopts = ["--cov=src", "--cov-branch", "--cov-report=xml", "-p", "no:cacheprovider"]

[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
fail_under = {THRESHOLD}

[tool.ruff]
line-length = 100

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.mypy]
strict = true
"""
COVERED = "def covered(x: int) -> int:\n    if x:\n        return 1\n    return 2\n"
UNCOVERED = "def uncovered(x: int) -> int:\n    if x:\n        return 1\n    return 2\n"
SPAGHETTI = (
    "def spaghetti(x: int) -> int:\n"
    + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(12))
    + "    return 0\n"
)
TEST = (
    "from pkg.a import covered\n\n\ndef test_covered() -> None:\n"
    "    assert covered(1) == 1\n    assert covered(0) == 2\n"
)
BASE: Mapping[str, bytes] = {
    "pyproject.toml": PYPROJECT.encode(),
    "src/pkg/__init__.py": b"",
    "src/pkg/a.py": COVERED.encode(),
    "tests/test_a.py": TEST.encode(),
}


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    tool, *rest = args
    return subprocess.run(  # noqa: S603
        [str(BIN / tool), *rest], cwd=repo, capture_output=True, text=True, check=False
    )


def changed_line_coverage(repo: Path, base: str) -> int:
    run(repo, "pytest", "-q")
    done = run(
        repo,
        "diff-cover",
        "coverage.xml",
        f"--compare-branch={base}",
        "--include-untracked",
        f"--fail-under={THRESHOLD}",
    )
    return done.returncode


def scenario(repo: Path, files: Mapping[str, bytes]) -> int:
    base = commit(repo, BASE)
    for path, data in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_bytes(data)
    return changed_line_coverage(repo, base)


@pytest.mark.requirement("REQ-2026-010-F04")
@pytest.mark.parametrize(
    ("name", "files", "failed"),
    [
        ("L1-E31", {"src/pkg/a.py": (COVERED + "\n\n" + UNCOVERED).encode()}, True),
        ("L1-E28", {"src/pkg/__init__.py": UNCOVERED.encode()}, True),
        ("untracked-new-file", {"src/pkg/new.py": UNCOVERED.encode()}, True),
        (
            "L1-E32",
            {
                "src/pkg/a.py": b"from pkg.b import covered as covered\n",
                "src/pkg/b.py": COVERED.encode(),
            },
            False,
        ),
        (
            "test-only-lines-ignored",
            {"tests/test_b.py": b"def test_b() -> None:\n    assert 1\n"},
            False,
        ),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_changed_line_coverage(
    root: Path,  # noqa: F811
    name: str,
    files: Mapping[str, bytes],
    *,
    failed: bool,
) -> None:
    assert (scenario(root, files) != 0) is failed


@pytest.mark.requirement("REQ-2026-010-F04")
def test_moving_an_uncovered_function_fails(root: Path) -> None:  # noqa: F811
    """L1-E33: the moved lines count as new lines, so they need a test."""
    unmoved = {**BASE, "src/pkg/a.py": (COVERED + "\n\n" + UNCOVERED).encode()}
    base = commit(root, unmoved)
    (root / "src/pkg/a.py").write_bytes(COVERED.encode())
    (root / "src/pkg/b.py").write_bytes(UNCOVERED.encode())
    assert changed_line_coverage(root, base) != 0


@pytest.mark.requirement("REQ-2026-010-F04")
@pytest.mark.parametrize(
    ("tool", "args", "files"),
    [
        ("ruff", ["check", "src"], {"src/pkg/a.py": b"import os\n"}),
        (
            "ruff",
            ["check", "--select", "C90", "src"],
            {"src/pkg/a.py": SPAGHETTI.encode()},
        ),
        ("mypy", ["src"], {"src/pkg/a.py": b"def f() -> int:\n    return 'x'\n"}),
        (
            "vulture",
            ["src", "tests", "--min-confidence", "60"],
            {"src/pkg/a.py": UNCOVERED.encode()},
        ),
        ("pytest", ["-q"], {"tests/test_a.py": b"def test_a() -> None:\n    assert 0\n"}),
        ("pytest", ["-q"], {"tests/test_a.py": b"def test_a() -> None:\n    assert 1\n"}),
    ],
    ids=["lint", "complexity", "types", "dead-code", "test-failure", "coverage-below-threshold"],
)
def test_quality_tools_reject(
    root: Path,  # noqa: F811
    tool: str,
    args: list[str],
    files: Mapping[str, bytes],
) -> None:
    """L1-E26: each tool rejects the corresponding defect, with this configuration."""
    commit(root, BASE)
    assert run(root, tool, *args).returncode == 0
    for path, data in files.items():
        (root / path).write_bytes(data)
    assert run(root, tool, *args).returncode != 0
