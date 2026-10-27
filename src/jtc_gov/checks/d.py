import re
from collections.abc import Sequence

from jtc_gov.derive.approvals import (
    APPROVAL_PATH,
    load_approvals,
    parse_approval,
    spec_tags,
    validity,
)
from jtc_gov.derive.markers import test_functions
from jtc_gov.domain.gates import DELIVERABLES
from jtc_gov.domain.models import Approval, ApprovalState, Change, Finding, ParseFailure
from jtc_gov.domain.repo import Repo

_TEST_FILE = re.compile(r"^tests/(?:.*/)?test_[^/]*\.py\Z")


def _tested_tags(repo: Repo) -> set[str]:
    tags: set[str] = set()
    for path in repo.list("head"):
        raw = repo.read(path, "head") if _TEST_FILE.match(path) else None
        funcs = test_functions(raw) if raw is not None else []
        if not isinstance(funcs, ParseFailure):
            tags |= {t for f in funcs for t in f.tags}
    return tags


def _check_open(repo: Repo, approval: Approval) -> list[Finding]:
    req = approval.requirement
    findings = [
        Finding("D.a", f".specs/{req}/{name}", "ゲートのペアがそろっていない")
        for d in DELIVERABLES
        for name in (d.design, d.test_spec)
        if not repo.read(f".specs/{req}/{name}", "head")
    ]
    findings += [
        Finding("D.b", f".specs/{req}", f"{r.kind}: {r.detail}")
        for r in validity(repo, "head", approval)
        if r.kind in ("set", "hash")
    ]
    return findings


def _check_closed(repo: Repo, approval: Approval) -> list[Finding]:
    req = approval.requirement
    if repo.read(f".specs/{req}/01_req_spec.md", "head") is None:
        return [Finding("D.c", f".specs/{req}", "仕様(01_req_spec.md)がない")]
    tags = spec_tags(repo, "head", req)
    if isinstance(tags, ParseFailure):
        return [Finding("D.c", f".specs/{req}", f"仕様が読めない: {tags.reason}")]
    tested = _tested_tags(repo)
    return [Finding("D.c", f".specs/{req}", f"{t} にテストがない") for t in sorted(tags - tested)]


def check_d(repo: Repo, changes: Sequence[Change]) -> list[Finding]:
    findings: list[Finding] = []
    touched = False
    for change in changes:
        if (
            change.old_path
            and APPROVAL_PATH.match(change.old_path)
            and change.status
            in (
                "deleted",
                "renamed",
            )
        ):
            findings.append(
                Finding("D.delete", change.old_path, "承認ファイルは削除・改名できない")
            )
            touched = True
        path = change.new_path
        m = APPROVAL_PATH.match(path) if path else None
        if not (path and m):
            continue
        touched = True
        raw = repo.read(path, "head")
        approval = parse_approval(raw, m.group(1)) if raw is not None else None
        if isinstance(approval, ParseFailure):
            findings.append(Finding("D.parse", path, approval.reason))
        elif approval and approval.state is ApprovalState.OPEN:
            findings += _check_open(repo, approval)
        elif approval and approval.state is ApprovalState.CLOSED:
            findings += _check_closed(repo, approval)
    if touched:
        opens = [
            a
            for a in load_approvals(repo, "head").values()
            if isinstance(a, Approval) and a.state is ApprovalState.OPEN
        ]
        if len(opens) >= 2:  # noqa: PLR2004
            findings.append(Finding("D.d", None, f"open な承認が {len(opens)} 個ある"))
    return findings
