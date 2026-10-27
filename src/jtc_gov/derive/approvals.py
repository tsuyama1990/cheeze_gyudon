import json
import re
from dataclasses import dataclass
from typing import Any, Final, Literal

from pydantic import ValidationError

from jtc_gov.derive.hashing import sha256_hex
from jtc_gov.domain.gates import APPROVAL_FILE, APPROVED_FILE_PATTERN, SPEC_FILE
from jtc_gov.domain.ids import FEATURE_TAG
from jtc_gov.domain.models import Approval, ApprovalState, ParseFailure, Ref
from jtc_gov.domain.repo import Repo

APPROVAL_PATH: Final = re.compile(rf"^\.specs/(REQ-\d{{4}}-\d{{3,}})/{re.escape(APPROVAL_FILE)}\Z")
_SPEC_TAG_LINE: Final = re.compile(r"^\s*[-*]\s+\*\*\[(REQ-\d{4}-\d{3,}-F\d{2,})\]")
_FENCE: Final = "```"


@dataclass(frozen=True)
class Reason:
    kind: Literal["state", "set", "hash"]
    detail: str


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [k for k, _ in pairs]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        msg = f"duplicate keys: {sorted(dup)}"
        raise ValueError(msg)
    return dict(pairs)


def parse_approval(raw: bytes, dir_name: str) -> Approval | ParseFailure:
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
        approval = Approval.model_validate(data)
    except (ValueError, ValidationError) as e:
        return ParseFailure(str(e))
    if approval.requirement != dir_name:
        return ParseFailure(f"requirement {approval.requirement} != directory {dir_name}")
    return approval


def load_approvals(repo: Repo, ref: Ref) -> dict[str, Approval | ParseFailure]:
    found: dict[str, Approval | ParseFailure] = {}
    for path in repo.list(ref):
        m = APPROVAL_PATH.match(path)
        raw = repo.read(path, ref) if m else None
        if m and raw is not None:
            found[m.group(1)] = parse_approval(raw, m.group(1))
    return found


def _approved_names(repo: Repo, ref: Ref, req: str) -> set[str]:
    prefix = f".specs/{req}/"
    return {
        p.removeprefix(prefix)
        for p in repo.list(ref)
        if p.startswith(prefix) and APPROVED_FILE_PATTERN.match(p.removeprefix(prefix))
    }


def validity(repo: Repo, ref: Ref, approval: Approval) -> list[Reason]:
    reasons: list[Reason] = []
    if approval.state is not ApprovalState.OPEN:
        reasons.append(Reason("state", approval.state.value))
    present = _approved_names(repo, ref, approval.requirement)
    listed = set(approval.files)
    reasons += [Reason("set", f"missing: {n}") for n in sorted(listed - present)]
    reasons += [Reason("set", f"extra: {n}") for n in sorted(present - listed)]
    for name, digest in sorted(approval.files.items()):
        raw = repo.read(f".specs/{approval.requirement}/{name}", ref)
        if raw is None or sha256_hex(raw) != digest:
            reasons.append(Reason("hash", name))
    return reasons


def valid_open(repo: Repo, ref: Ref) -> list[Approval]:
    return [
        a
        for a in load_approvals(repo, ref).values()
        if isinstance(a, Approval) and not validity(repo, ref, a)
    ]


def spec_tags(repo: Repo, ref: Ref, req: str) -> set[str] | ParseFailure:
    raw = repo.read(f".specs/{req}/{SPEC_FILE}", ref)
    if raw is None:
        return set()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return ParseFailure(str(e))
    tags: set[str] = set()
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
        elif not fenced and (m := _SPEC_TAG_LINE.match(line)) and FEATURE_TAG.match(m.group(1)):
            tags.add(m.group(1))
    return tags
