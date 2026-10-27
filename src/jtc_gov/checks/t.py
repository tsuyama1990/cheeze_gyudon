from collections.abc import Sequence

from jtc_gov.derive.approvals import spec_tags
from jtc_gov.derive.markers import TestFunction, test_functions
from jtc_gov.domain.gates import TEST_FILENAME, is_test_path
from jtc_gov.domain.ids import FEATURE_TAG, requirement_of
from jtc_gov.domain.models import Change, Finding, ParseFailure
from jtc_gov.domain.repo import Repo


def _check_function(repo: Repo, path: str, f: TestFunction) -> list[Finding]:
    where = f"{path}::{f.qualname}"
    findings = [
        Finding("T.a", where, f"形式不正のタグ: {t}") for t in f.tags if not FEATURE_TAG.match(t)
    ]
    valid = [t for t in f.tags if FEATURE_TAG.match(t)]
    if not valid:
        reason = (
            "リテラルでない引数" if f.has_marker and not f.tags else "requirement marker がない"
        )
        if not findings:
            findings.append(Finding("T.a", where, reason))
        return findings
    for tag in valid:
        spec = spec_tags(repo, "head", requirement_of(tag))
        if isinstance(spec, ParseFailure) or tag not in spec:
            findings.append(Finding("T.b", where, f"{tag} が仕様にない"))
    return findings


def check_t(repo: Repo, changes: Sequence[Change]) -> list[Finding]:
    del changes
    findings: list[Finding] = []
    for path in repo.list("head"):
        if not TEST_FILENAME.match(path):
            continue
        if not is_test_path(path):
            findings.append(Finding("T.c", path, "テストは tests/ に置く"))
            continue
        raw = repo.read(path, "head")
        funcs = test_functions(raw) if raw is not None else []
        if isinstance(funcs, ParseFailure):
            findings.append(Finding("T.a", path, f"解析できない: {funcs.reason}"))
            continue
        for f in funcs:
            findings += _check_function(repo, path, f)
    return findings
