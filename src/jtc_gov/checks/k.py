import re
from collections.abc import Sequence

from jtc_gov.derive.approvals import valid_open
from jtc_gov.derive.changes import related_requirements
from jtc_gov.domain.gates import APPROVAL_FILE, GUARDED_PREFIX
from jtc_gov.domain.models import Change, Finding
from jtc_gov.domain.repo import Repo

_SRC = "src/"
_AUX = ("tests/", ".specs/")


def _touches(changes: Sequence[Change], prefixes: tuple[str, ...]) -> bool:
    return any(p.startswith(prefixes) for c in changes for p in c.paths())


def _guarded(path: str, req: str) -> bool:
    prefix = f".specs/{req}/"
    if not path.startswith(prefix):
        return False
    rest = path.removeprefix(prefix)
    return rest == APPROVAL_FILE or bool(re.match(GUARDED_PREFIX, rest))


def check_k(repo: Repo, changes: Sequence[Change]) -> list[Finding]:
    if not (_touches(changes, (_SRC,)) and _touches(changes, _AUX)):
        return []
    opens = valid_open(repo, "base")
    if len(opens) != 1:
        return [
            Finding("K.a", None, f"有効な承認が {len(opens)} 個", "open な承認がちょうど 1 つ必要")
        ]
    req = opens[0].requirement
    findings = [
        Finding("K.b", p, "承認済みの設計ファイルは、実装の PR で変更できない")
        for c in changes
        for p in c.paths()
        if _guarded(p, req)
    ]
    findings += [
        Finding("K.c", None, f"要件 {r} は承認された要件の外", f"承認された要件は {req}")
        for r in sorted(related_requirements(repo, changes) - {req})
    ]
    return findings
