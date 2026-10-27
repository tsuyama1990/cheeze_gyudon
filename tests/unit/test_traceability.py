import re
from pathlib import Path

import pytest

TESTS = Path(__file__).parents[1]
SPECS = TESTS.parents[0] / ".specs" / "REQ-2026-010"
PLAN_FILES = {
    "02_system_tests.md": r"L1-[A-Z]\d+",
    "03_integration_tests.md": r"L2-I\d+",
    "04_unit_tests.md": r"L3-U\d+",
}
MANUAL = {"L1-C01", "L1-C03", "L1-C06", "L1-M01"}


def planned() -> set[str]:
    ids: set[str] = set()
    for name, pattern in PLAN_FILES.items():
        text = (SPECS / name).read_text(encoding="utf-8")
        ids |= set(re.findall(rf"^\| ({pattern}) \|", text, re.MULTILINE))
    return ids


def referenced() -> set[str]:
    pattern = re.compile(r"(?<![\w-])(L[123]-[A-Z]\d+)(?!\d)")
    found: set[str] = set()
    for path in TESTS.rglob("test_*.py"):
        if path.name != Path(__file__).name:
            found |= set(pattern.findall(path.read_text(encoding="utf-8")))
    return found


@pytest.mark.requirement("REQ-2026-010-F08")
def test_every_planned_test_has_an_implementation() -> None:
    """The test plans (02, 03, 04) and the tests move together: a plan row needs a test."""
    missing = sorted(planned() - MANUAL - referenced())
    assert missing == []


@pytest.mark.requirement("REQ-2026-010-F08")
def test_tests_refer_only_to_planned_rows() -> None:
    stale = sorted(referenced() - planned())
    assert stale == []


@pytest.mark.requirement("REQ-2026-010-F08")
def test_manual_rows_are_planned_rows() -> None:
    assert planned() >= MANUAL
