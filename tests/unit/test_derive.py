import pytest

from jtc_gov.derive.approvals import (
    load_approvals,
    parse_approval,
    spec_tags,
    valid_open,
    validity,
)
from jtc_gov.derive.changes import related_requirements
from jtc_gov.derive.gates import display_gate
from jtc_gov.derive.hashing import sha256_hex
from jtc_gov.derive.markers import TestFunction
from jtc_gov.derive.markers import test_functions as extract
from jtc_gov.domain.models import Approval, ParseFailure
from tests.support.fake_repo import FakeRepo, approval_json, design_files, with_approval

REQ = "REQ-2026-010"
T = "REQ-2026-010-F01"


@pytest.mark.requirement("REQ-2026-010-F01")
def test_sha256_hex() -> None:
    empty = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert sha256_hex(b"") == empty
    assert sha256_hex(b"a\n") != sha256_hex(b"a\r\n")


def _ok(req: str = REQ, state: str = "open") -> bytes:
    return approval_json(req, state, {"01_req_spec.md": b"x"})


@pytest.mark.requirement("REQ-2026-010-F02")
@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"",
        _ok("REQ-2026-011"),
        b'{"requirement": "REQ-2026-010", "state": "open", "state": "closed", "files": {}}',
        b"\xff\xfe",
        b'{"requirement": "REQ-2026-010", "state": "bad", "files": {}}',
    ],
)
def test_parse_approval_failures(raw: bytes) -> None:
    assert isinstance(parse_approval(raw, REQ), ParseFailure)


@pytest.mark.requirement("REQ-2026-010-F02")
def test_parse_approval_ok() -> None:
    assert isinstance(parse_approval(_ok(), REQ), Approval)


@pytest.mark.requirement("REQ-2026-010-F02")
def test_load_approvals_reads_exact_paths_only() -> None:
    files = {
        f".specs/{REQ}/approval.json": _ok(),
        ".specs/REQ-2026-011/approval.json": b"broken",
        f".specs/{REQ}/approval.json.bak": _ok(),
        f".specs/{REQ}/x/approval.json": _ok(),
    }
    loaded = load_approvals(FakeRepo({}, files), "head")
    assert set(loaded) == {REQ, "REQ-2026-011"}
    assert isinstance(loaded[REQ], Approval)
    assert isinstance(loaded["REQ-2026-011"], ParseFailure)


def _approval(repo: FakeRepo) -> Approval:
    a = load_approvals(repo, "head")[REQ]
    assert isinstance(a, Approval)
    return a


@pytest.mark.requirement("REQ-2026-010-F01")
def test_validity_all_match() -> None:
    repo = FakeRepo({}, with_approval(REQ))
    assert validity(repo, "head", _approval(repo)) == []


@pytest.mark.requirement("REQ-2026-010-F01")
def test_validity_reports_each_problem() -> None:
    files = with_approval(REQ, "closed")
    files[f".specs/{REQ}/05_new.md"] = b"x"
    files[f".specs/{REQ}/02_system_design.md"] = b"changed"
    del files[f".specs/{REQ}/03_architecture.md"]
    repo = FakeRepo({}, files)
    kinds = {(r.kind, r.detail.split(": ")[-1]) for r in validity(repo, "head", _approval(repo))}
    assert kinds == {
        ("state", "closed"),
        ("set", "05_new.md"),
        ("set", "03_architecture.md"),
        ("hash", "02_system_design.md"),
        ("hash", "03_architecture.md"),
    }


@pytest.mark.requirement("REQ-2026-010-F01")
def test_valid_open_filters() -> None:
    other = with_approval("REQ-2026-011", "closed")
    broken = {".specs/REQ-2026-012/approval.json": b"x"}
    stale = with_approval("REQ-2026-013")
    stale[".specs/REQ-2026-013/05_extra.md"] = b"x"
    files = {**with_approval(REQ), **other, **broken, **stale}
    assert [a.requirement for a in valid_open(FakeRepo({}, files), "head")] == [REQ]
    assert valid_open(FakeRepo({}, {}), "head") == []


def _spec(text: str | bytes | None) -> FakeRepo:
    files = (
        {}
        if text is None
        else {f".specs/{REQ}/01_req_spec.md": text.encode() if isinstance(text, str) else text}
    )
    return FakeRepo({}, files)


@pytest.mark.requirement("REQ-2026-010-F03")
def test_spec_tags() -> None:
    text = (
        "- **[REQ-2026-010-F01] a**\n* **[REQ-2026-010-F02]**\n"
        "本文 [REQ-2026-010-F03]\n```\n- **[REQ-2026-010-F04] in fence**\n```\n"
        "- **[BAD-F05]**\n- **[REQ-2026-010-F01] dup**\n"
    )
    assert spec_tags(_spec(text), "head", REQ) == {"REQ-2026-010-F01", "REQ-2026-010-F02"}
    assert spec_tags(_spec(None), "head", REQ) == set()
    assert isinstance(spec_tags(_spec(b"\xff"), "head", REQ), ParseFailure)


def _funcs(src: str) -> list[TestFunction]:
    result = extract(src.encode())
    assert not isinstance(result, ParseFailure)
    return result


@pytest.mark.requirement("REQ-2026-010-F03")
def test_test_functions_extraction() -> None:
    src = """
def test_a(): pass
async def test_async(): pass
def helper(): pass
def test_a(): pass
class TestK:
    def test_m(self):
        def test_inner(): pass
class Other:
    def test_x(self): pass
if True:
    def test_cond(): pass
for _ in []:
    def test_loop(): pass
try:
    def test_try(): pass
except Exception:
    pass
while False:
    def test_while(): pass
match 1:
    case 1:
        def test_match(): pass
def f():
    def test_nested(): pass
"""
    names = [f.qualname for f in _funcs(src)]
    assert names == [
        "test_a",
        "test_async",
        "test_a#2",
        "TestK.test_m",
        "test_cond",
        "test_loop",
        "test_try",
        "test_while",
        "test_match",
    ]


@pytest.mark.requirement("REQ-2026-010-F03")
def test_test_functions_markers() -> None:
    src = """
import pytest
pytestmark = [pytest.mark.requirement("REQ-2026-010-F09")]
@pytest.mark.requirement("A")
def test_literal(): pass
@requirement("B")
@pytest.mark.requirement("C")
def test_multi(): pass
@pytest.mark.requirement(VAR)
def test_var(): pass
@pytest.mark.requirement()
def test_noarg(): pass
@pytest.mark.slow
def test_other(): pass
@pytest.mark.requirement("K")
class TestC:
    def test_m(self): pass
"""
    by = {f.qualname: f for f in _funcs(src)}
    nine = "REQ-2026-010-F09"
    assert by["test_literal"].tags == (nine, "A")
    assert by["test_multi"].tags == (nine, "B", "C")
    assert by["test_var"].has_marker
    assert by["test_var"].tags == (nine,)
    assert by["test_noarg"].has_marker
    assert by["test_other"].tags == (nine,)
    assert by["TestC.test_m"].tags == (nine, "K")


@pytest.mark.requirement("REQ-2026-010-F03")
def test_test_functions_single_pytestmark() -> None:
    funcs = _funcs('pytestmark = pytest.mark.requirement("T")\ndef test_a(): pass\n')
    assert funcs[0].tags == ("T",)
    assert not _funcs("def test_a(): pass")[0].has_marker


@pytest.mark.requirement("REQ-2026-010-F01")
def test_test_functions_source_range() -> None:
    base = '@pytest.mark.parametrize(\n    "x",\n    [1],\n)\ndef test_a(x):\n    assert x == 1\n'
    sha = _funcs(base)[0].source_sha
    assert _funcs("# comment\n" + base)[0].source_sha == sha
    assert _funcs(base.replace("== 1", "== 2"))[0].source_sha != sha
    assert _funcs(base.replace('"x"', '"y"'))[0].source_sha != sha


@pytest.mark.requirement("REQ-2026-010-F03")
def test_test_functions_failures() -> None:
    assert isinstance(extract(b"def ("), ParseFailure)
    assert isinstance(extract(b"\xff\xfe = 1"), ParseFailure)
    assert extract(b"") == []


def _test_src(mark: str, body: str = "pass") -> bytes:
    return f'@pytest.mark.requirement("{mark}")\ndef test_a():\n    {body}\n'.encode()


def _rel(
    base: dict[str, bytes], head: dict[str, bytes], renames: dict[str, str] | None = None
) -> set[str]:
    repo = FakeRepo(base, head, renames)
    return related_requirements(repo, repo.changes())


@pytest.mark.requirement("REQ-2026-010-F01")
def test_related_requirements_specs_and_functions() -> None:
    p = "tests/test_x.py"
    assert _rel({}, {f".specs/{REQ}/x.md": b"a"}) == {REQ}
    assert _rel({}, {p: _test_src(T)}) == {REQ}
    assert _rel({p: _test_src(T)}, {}) == {REQ}
    assert _rel({p: _test_src(T)}, {p: _test_src("REQ-2026-001-F01")}) == {REQ, "REQ-2026-001"}
    assert _rel({p: _test_src(T)}, {p: _test_src(T)}) == set()
    assert _rel({p: _test_src(T)}, {p: _test_src(T, "assert 1")}) == {REQ}


@pytest.mark.requirement("REQ-2026-010-F01")
def test_related_requirements_class_and_module_marks() -> None:
    p = "tests/test_x.py"

    def cls(m: str) -> bytes:
        return (
            f'@pytest.mark.requirement("{m}")\nclass TestC:\n    def test_m(self): pass\n'.encode()
        )

    def mod(m: str) -> bytes:
        return f'pytestmark = pytest.mark.requirement("{m}")\ndef test_a(): pass\n'.encode()

    assert _rel({p: cls(T)}, {p: cls("REQ-2026-001-F01")}) == {REQ, "REQ-2026-001"}
    assert _rel({p: mod(T)}, {p: mod("REQ-2026-001-F01")}) == {REQ, "REQ-2026-001"}


@pytest.mark.requirement("REQ-2026-010-F01")
def test_related_requirements_mixed_file_and_rename_and_errors() -> None:
    p = "tests/test_x.py"
    mixed = (
        b'@pytest.mark.requirement("REQ-2026-001-F01")\ndef test_a(): pass\n'
        b'@pytest.mark.requirement("REQ-2026-010-F01")\ndef test_b(): pass\n'
    )
    assert _rel({p: mixed}, {p: mixed + b"\n# c\n"}) == set()
    assert _rel(
        {p: mixed}, {p: mixed.replace(b"def test_b(): pass", b"def test_b(): assert 1")}
    ) == {REQ}
    assert _rel({p: mixed}, {"tests/test_y.py": mixed}, {p: "tests/test_y.py"}) == set()
    assert _rel({p: b"def ("}, {p: b"def (("}) == set()
    bad_tag = b'@pytest.mark.requirement("nope")\ndef test_a(): pass\n'
    assert _rel({}, {p: bad_tag}) == set()


@pytest.mark.requirement("REQ-2026-010-F06")
def test_display_gate() -> None:
    def gate(files: dict[str, bytes]) -> int:
        return display_gate(FakeRepo({}, files), "head", REQ)

    full = design_files(REQ)
    assert gate({}) == 1
    only_design = {k: v for k, v in full.items() if k.endswith("01_req_spec.md")}
    assert gate(only_design) == 1
    first_two = {k: v for k, v in full.items() if k.rsplit("/", 1)[1][:2] in ("01", "02")}
    assert gate(first_two) == 3
    assert gate(full) == 5
    assert gate({**full, f".specs/{REQ}/04_unit_tests.md": b""}) == 4
