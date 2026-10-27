import re
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Deliverable:
    gate: int
    design: str
    test_spec: str


DELIVERABLES: Final = (
    Deliverable(1, "01_req_spec.md", "01_acceptance_tests.feature"),
    Deliverable(2, "02_system_design.md", "02_system_tests.md"),
    Deliverable(3, "03_architecture.md", "03_integration_tests.md"),
    Deliverable(4, "04_detail_design.md", "04_unit_tests.md"),
)
APPROVAL_FILE: Final = "approval.json"
APPROVED_FILE_PATTERN: Final = re.compile(r"^0[1-5]_[^/]+\Z")
GUARDED_PREFIX: Final = re.compile(r"^0[1-5]_")
SRC_PREFIX: Final = "src/"
