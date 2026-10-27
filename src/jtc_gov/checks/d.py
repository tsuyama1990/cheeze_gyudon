from collections.abc import Sequence

from jtc_gov.derive.approvals import (
    APPROVAL_PATH,
    load_approvals,
    parse_approval,
    spec_tags,
    validity,
)
from jtc_gov.derive.markers import test_functions
from jtc_gov.domain.gates import DELIVERABLES, GUARDED_PREFIX, SPEC_FILE, is_test_path
from jtc_gov.domain.models import Approval, ApprovalState, Change, Finding, ParseFailure, Ref
from jtc_gov.domain.repo import Repo


def _tested_tags(repo: Repo) -> set[str]:
    tags: set[str] = set()
    for path in repo.list("head"):
        raw = repo.read(path, "head") if is_test_path(path) else None
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


def _changed_design_files(repo: Repo, req: str) -> list[Finding]:
    prefix = f".specs/{req}/"
    names = {
        p
        for ref in ("base", "head")
        for p in repo.list(ref)
        if p.startswith(prefix) and GUARDED_PREFIX.match(p.removeprefix(prefix))
    }
    return [
        Finding("D.c", p, "承認済みの設計は、完了の PR で変更できない")
        for p in sorted(names)
        if repo.read(p, "base") != repo.read(p, "head")
    ]


def _check_closed(repo: Repo, approval: Approval) -> list[Finding]:
    req = approval.requirement
    previous = load_approvals(repo, "base").get(req)
    completing = False
    if isinstance(previous, Approval):
        if previous.state is ApprovalState.WITHDRAWN:
            return [
                Finding(
                    "D.c", f".specs/{req}", "取り下げた要件は直接閉じられない(先に open に戻す)"
                )
            ]
        completing = previous.state is ApprovalState.OPEN
        if completing and validity(repo, "base", previous):
            return [Finding("D.c", f".specs/{req}", "承認が失効している(更新してから閉じる)")]
    ref: Ref = "base" if completing else "head"
    findings = _changed_design_files(repo, req) if completing else []
    if repo.read(f".specs/{req}/{SPEC_FILE}", ref) is None:
        return [*findings, Finding("D.c", f".specs/{req}", f"仕様({SPEC_FILE})がない")]
    tags = spec_tags(repo, ref, req)
    if isinstance(tags, ParseFailure):
        return [*findings, Finding("D.c", f".specs/{req}", f"仕様が読めない: {tags.reason}")]
    tested = _tested_tags(repo)
    return findings + [
        Finding("D.c", f".specs/{req}", f"{t} にテストがない") for t in sorted(tags - tested)
    ]


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
