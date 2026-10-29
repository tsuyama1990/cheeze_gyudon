import json
import re
from collections.abc import Container
from pathlib import Path

SPECS = Path(__file__).parents[2] / ".specs"
CLOSED = "closed"
PLAN_FILES = {
    "02_system_tests.md": r"L1-[A-Z]\d+",
    "03_integration_tests.md": r"L2-I\d+",
    "04_unit_tests.md": r"L3-U\d+",
}
# Plan rows that are checked by hand. Add a requirement here when it gets approved.
MANUAL_ROWS = {
    "REQ-2026-010": {"L1-C01", "L1-C03", "L1-C06", "L1-M01"},
}


def approval_states() -> dict[str, str]:
    return {
        p.parent.name: json.loads(p.read_text(encoding="utf-8"))["state"]
        for p in sorted(SPECS.glob("REQ-*/approval.json"))
    }


def designed_modules(states: Container[str] | None = None) -> set[str]:
    """Modules named in the detail designs; only requirements in `states` if given."""
    approved = approval_states()
    return {
        heading
        for design in SPECS.glob("REQ-*/04_detail_design.md")
        if states is None or approved.get(design.parent.name) in states
        for heading in re.findall(
            r"^### [\d.a-z]+ `([a-z_/]+\.py)`", design.read_text(encoding="utf-8"), re.MULTILINE
        )
    }


def planned_rows(req: str) -> set[str]:
    ids: set[str] = set()
    for name, pattern in PLAN_FILES.items():
        plan = SPECS / req / name
        if plan.is_file():
            ids |= set(
                re.findall(rf"^\| ({pattern}) \|", plan.read_text(encoding="utf-8"), re.MULTILINE)
            )
    return ids
