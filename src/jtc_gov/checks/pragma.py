from collections import Counter
from collections.abc import Sequence

from jtc_gov.domain.gates import SRC_PREFIX
from jtc_gov.domain.models import Change, Finding, Ref
from jtc_gov.domain.repo import Repo

_MARK = "pragma: no cover"


def _is_src(path: str | None) -> bool:
    return path is not None and path.startswith(SRC_PREFIX) and path.endswith(".py")


def _lines(repo: Repo, path: str, ref: Ref) -> list[str] | None:
    raw = repo.read(path, ref)
    if raw is None:
        return None
    try:
        return raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None


def _count(repo: Repo, paths: set[str], ref: Ref) -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in paths:
        counts.update(line.strip() for line in _lines(repo, path, ref) or [] if _MARK in line)
    return counts


def check_pragma(repo: Repo, changes: Sequence[Change]) -> list[Finding]:
    old = {c.old_path for c in changes if c.old_path and _is_src(c.old_path)}
    new = {c.new_path for c in changes if c.new_path and _is_src(c.new_path)}
    before, after = _count(repo, old, "base"), _count(repo, new, "head")
    findings: list[Finding] = []
    for text, n in after.items():
        excess = n - before.get(text, 0)
        if excess <= 0:
            continue
        spots = [
            f"{p}:{i}"
            for p in sorted(new)
            for i, line in enumerate(_lines(repo, p, "head") or [], 1)
            if line.strip() == text
        ]
        findings += [
            Finding("Q.pragma", where, f"{_MARK} が増えた: {text}") for where in spots[-excess:]
        ]
    return findings
