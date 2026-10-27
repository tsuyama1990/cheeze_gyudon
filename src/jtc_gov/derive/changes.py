import re
from collections.abc import Sequence
from typing import Final

from jtc_gov.derive.markers import TestFunction, test_functions
from jtc_gov.domain.ids import FEATURE_TAG, requirement_of
from jtc_gov.domain.models import Change, ParseFailure, Ref
from jtc_gov.domain.repo import Repo

SPEC_PATH: Final = re.compile(r"^\.specs/(REQ-\d{4}-\d{3,})/")
TEST_FILE: Final = re.compile(r"^tests/(?:.*/)?test_[^/]*\.py\Z")


def _functions(repo: Repo, path: str | None, ref: Ref) -> dict[str, TestFunction]:
    raw = repo.read(path, ref) if path is not None else None
    parsed = test_functions(raw) if raw is not None else []
    if isinstance(parsed, ParseFailure):
        return {}
    return {f.qualname: f for f in parsed}


def _requirements(funcs: Sequence[TestFunction]) -> set[str]:
    return {requirement_of(t) for f in funcs for t in f.tags if FEATURE_TAG.match(t)}


def related_requirements(repo: Repo, changes: Sequence[Change]) -> set[str]:
    found: set[str] = set()
    for change in changes:
        found |= {m.group(1) for p in change.paths() if (m := SPEC_PATH.match(p))}
        if not any(TEST_FILE.match(p) for p in change.paths()):
            continue
        old = _functions(repo, change.old_path, "base")
        new = _functions(repo, change.new_path, "head")
        for name in old.keys() | new.keys():
            before, after = old.get(name), new.get(name)
            if (
                before is None
                or after is None
                or (before.source_sha, before.tags)
                != (
                    after.source_sha,
                    after.tags,
                )
            ):
                found |= _requirements([f for f in (before, after) if f is not None])
    return found
