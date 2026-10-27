import re
from collections.abc import Sequence
from typing import Final

from jtc_gov.derive.markers import TestFunction, test_functions
from jtc_gov.domain.gates import is_test_path
from jtc_gov.domain.ids import FEATURE_TAG, requirement_of
from jtc_gov.domain.models import Change, ParseFailure, Ref
from jtc_gov.domain.repo import Repo

SPEC_PATH: Final = re.compile(r"^\.specs/(REQ-\d{4}-\d{3,})/")


def _functions(repo: Repo, path: str | None, ref: Ref) -> dict[str, TestFunction]:
    raw = repo.read(path, ref) if path is not None else None
    parsed = test_functions(raw) if raw is not None else []
    if isinstance(parsed, ParseFailure):
        return {}
    return {f.qualname: f for f in parsed}


def _requirements(funcs: Sequence[TestFunction]) -> set[str]:
    return {requirement_of(t) for f in funcs for t in f.tags if FEATURE_TAG.match(t)}


def _changed_pairs(
    repo: Repo, change: Change
) -> list[tuple[TestFunction | None, TestFunction | None]]:
    if not any(is_test_path(p) for p in change.paths()):
        return []
    old = _functions(repo, change.old_path, "base")
    new = _functions(repo, change.new_path, "head")
    pairs = [(old.get(name), new.get(name)) for name in sorted(old.keys() | new.keys())]
    return [
        (before, after)
        for before, after in pairs
        if before is None
        or after is None
        or (before.source_sha, before.tags) != (after.source_sha, after.tags)
    ]


def related_requirements(repo: Repo, changes: Sequence[Change]) -> set[str]:
    found: set[str] = set()
    for change in changes:
        found |= {m.group(1) for p in change.paths() if (m := SPEC_PATH.match(p))}
        for pair in _changed_pairs(repo, change):
            found |= _requirements([f for f in pair if f is not None])
    return found


def changed_test_functions(repo: Repo, changes: Sequence[Change]) -> bool:
    return any(after is not None for change in changes for _, after in _changed_pairs(repo, change))
