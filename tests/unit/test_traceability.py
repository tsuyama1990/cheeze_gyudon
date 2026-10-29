import re
from pathlib import Path

import pytest

from tests.support.specs import CLOSED, MANUAL_ROWS, approval_states, planned_rows

TESTS = Path(__file__).parents[1]
APPROVED = [req for req in sorted(approval_states()) if planned_rows(req)]
COMPLETED = [req for req in APPROVED if approval_states()[req] == CLOSED]


def referenced(req: str) -> set[str]:
    """Plan rows cited by the test files that carry this requirement's markers."""
    pattern = re.compile(r"(?<![\w-])(L[123]-[A-Z]\d+)(?!\d)")
    found: set[str] = set()
    for path in TESTS.rglob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name != Path(__file__).name and f'mark.requirement("{req}-F' in text:
            found |= set(pattern.findall(text))
    return found


@pytest.mark.requirement("REQ-2026-010-F08")
@pytest.mark.parametrize("req", COMPLETED)
def test_every_planned_test_has_an_implementation(req: str) -> None:
    """A closed requirement is complete: every plan row has a test or is checked by hand."""
    missing = sorted(planned_rows(req) - MANUAL_ROWS.get(req, set()) - referenced(req))
    assert missing == []


@pytest.mark.requirement("REQ-2026-010-F08")
@pytest.mark.parametrize("req", APPROVED)
def test_tests_refer_only_to_planned_rows(req: str) -> None:
    stale = sorted(referenced(req) - planned_rows(req))
    assert stale == []


@pytest.mark.requirement("REQ-2026-010-F08")
@pytest.mark.parametrize("req", APPROVED)
def test_manual_rows_are_planned_rows(req: str) -> None:
    assert planned_rows(req) >= MANUAL_ROWS.get(req, set())
