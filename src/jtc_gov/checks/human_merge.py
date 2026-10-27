from collections.abc import Sequence

from jtc_gov.derive.approvals import APPROVAL_PATH
from jtc_gov.domain.machinery import machinery_reason
from jtc_gov.domain.models import Change

_DECISION = "決定(approval.json)"


def human_merge(changes: Sequence[Change]) -> tuple[str, ...]:
    reasons: set[str] = set()
    for path in (p for c in changes for p in c.paths()):
        if reason := machinery_reason(path):
            reasons.add(reason)
        if APPROVAL_PATH.match(path):
            reasons.add(_DECISION)
    return tuple(sorted(reasons))
