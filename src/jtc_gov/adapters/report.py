import json

from jtc_gov.derive.approvals import load_approvals, valid_open, validity
from jtc_gov.derive.gates import display_gate
from jtc_gov.domain.models import Approval, ApprovalState, CheckResult, ParseFailure
from jtc_gov.domain.repo import Repo

_SHORT_MAX_LINES = 3


def format_findings(result: CheckResult) -> str:
    lines = [
        f"{f.rule} {f.path}: {f.message}" if f.path else f"{f.rule}: {f.message}"
        for f in result.findings
    ]
    if result.human_merge:
        lines.append(f"人間のマージが必要: {', '.join(result.human_merge)}")
    return "\n".join(lines)


def findings_json(result: CheckResult) -> str:
    return json.dumps(
        {
            "ok": result.ok,
            "findings": [
                {"rule": f.rule, "path": f.path, "message": f.message, "hint": f.hint}
                for f in result.findings
            ],
            "human_merge": list(result.human_merge),
        },
        ensure_ascii=False,
    )


def _approval_line(repo: Repo, req: str, approval: Approval | ParseFailure) -> str:
    if isinstance(approval, ParseFailure):
        return f"{req}: 承認ファイルが読めない ({approval.reason})"
    gate = display_gate(repo, "head", req)
    if approval.state is not ApprovalState.OPEN:
        return f"{req}: {approval.state.value} / ゲート {gate}"
    reasons = validity(repo, "head", approval)
    if reasons:
        detail = "; ".join(f"{r.kind}: {r.detail}" for r in reasons)
        return f"{req}: {approval.state.value} / 失効 ({detail}) / ゲート {gate}"
    return f"{req}: {approval.state.value} / 有効 / ゲート {gate}"


def _src_line(repo: Repo) -> str:
    opens = valid_open(repo, "base")
    if len(opens) == 1:
        return f"src/ の変更(テストまたは仕様を伴う): 可能 ({opens[0].requirement})"
    return f"src/ の変更(テストまたは仕様を伴う): 不可 (有効な open な承認が {len(opens)} 個)"


def format_status(repo: Repo, head_label: str) -> str:
    approvals = load_approvals(repo, "head")
    lines = [f"head: {head_label}"]
    lines += [_approval_line(repo, req, a) for req, a in sorted(approvals.items())]
    if not approvals:
        lines.append("要件なし")
    lines.append(_src_line(repo))
    return "\n".join(lines)


def short_status(repo: Repo) -> str:
    approvals = load_approvals(repo, "head")
    lines = [f"jtc-gov: 要件 {len(approvals)} 件、有効な open {len(valid_open(repo, 'head'))} 件"]
    broken = [
        req
        for req, a in sorted(approvals.items())
        if isinstance(a, ParseFailure) or (a.state.value == "open" and validity(repo, "head", a))
    ]
    if broken:
        lines.append(f"失効または読めない承認: {', '.join(broken)}")
    lines.append(_src_line(repo))
    return "\n".join(lines[:_SHORT_MAX_LINES])
