import pytest

from jtc_gov.checks import run_all
from jtc_gov.checks.d import check_d
from jtc_gov.checks.human_merge import human_merge
from jtc_gov.checks.k import check_k
from jtc_gov.checks.pragma import check_pragma
from jtc_gov.checks.t import check_t
from jtc_gov.domain.errors import RepoError
from jtc_gov.domain.models import Change, Finding
from tests.support.fake_repo import FakeRepo, approval_json, design_files, with_approval

REQ = "REQ-2026-010"
OTHER = "REQ-2026-001"
TAG = "REQ-2026-010-F01"
TEST = "tests/test_x.py"


def _t(tag: str, body: str = "pass") -> bytes:
    return f'@pytest.mark.requirement("{tag}")\ndef test_a():\n    {body}\n'.encode()


def _rules(findings: list[Finding]) -> list[str]:
    return [f.rule for f in findings]


def _k(base: dict[str, bytes], head: dict[str, bytes]) -> list[Finding]:
    repo = FakeRepo(base, head)
    return check_k(repo, repo.changes())


@pytest.mark.requirement("REQ-2026-010-F01")
def test_k_applies_only_with_src_and_aux() -> None:
    assert _k({}, {"src/a.py": b"x"}) == []
    assert _k({}, {TEST: _t(TAG)}) == []
    assert _rules(_k({}, {"src/a.py": b"x", TEST: _t(TAG)})) == ["K.a"]
    assert _rules(_k({}, {"src/a.py": b"x", ".specs/x/y.md": b"x"})) == ["K.a"]


@pytest.mark.requirement("REQ-2026-010-F01")
def test_k_a_counts_valid_opens() -> None:
    base = with_approval(REQ)
    head = {**base, "src/a.py": b"x", TEST: _t(TAG)}
    assert _k(base, head) == []
    two = {**base, **with_approval("REQ-2026-011")}
    assert _rules(_k(two, {**two, "src/a.py": b"x", TEST: _t(TAG)})) == ["K.a"]


@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.parametrize(
    ("edit", "hit"),
    [
        (f".specs/{REQ}/approval.json", True),
        (f".specs/{REQ}/02_system_design.md", True),
        (f".specs/{REQ}/05_new.md", True),
        (f".specs/{REQ}/01_notes/extra.md", True),
        (f".specs/{REQ}/notes.md", False),
        (f".specs/{REQ}/06_x.md", False),
    ],
)
def test_k_b(edit: str, *, hit: bool) -> None:
    base = with_approval(REQ)
    head = {**base, "src/a.py": b"x", edit: b"changed"}
    assert ("K.b" in _rules(_k(base, head))) is hit


@pytest.mark.requirement("REQ-2026-010-F01")
def test_k_b_rename() -> None:
    base = {**with_approval(REQ), "src/a.py": b"x"}
    head = {k: v for k, v in base.items() if k != f".specs/{REQ}/02_system_design.md"}
    head[f".specs/{REQ}/notes.md"] = base[f".specs/{REQ}/02_system_design.md"]
    repo = FakeRepo(base, head, {f".specs/{REQ}/02_system_design.md": f".specs/{REQ}/notes.md"})
    repo2 = FakeRepo(base, {**head, "src/a.py": b"y"}, repo._renames)  # noqa: SLF001
    assert "K.b" in _rules(check_k(repo2, repo2.changes()))


@pytest.mark.requirement("REQ-2026-010-F01")
def test_k_c() -> None:
    base = with_approval(REQ)
    src = {"src/a.py": b"x"}
    assert "K.c" in _rules(_k(base, {**base, **src, "tests/test_o.py": _t("REQ-2026-001-F01")}))
    assert "K.c" in _rules(_k(base, {**base, **src, f".specs/{OTHER}/x.md": b"x"}))
    removed = {**base, "tests/test_o.py": _t("REQ-2026-001-F01")}
    assert "K.c" in _rules(_k(removed, {**base, **src}))
    assert _k(base, {**base, **src, TEST: _t(TAG)}) == []


@pytest.mark.requirement("REQ-2026-010-F01")
def test_k_rename_from_src_counts_as_src() -> None:
    base = {**with_approval(REQ), "src/a.py": b"x"}
    head = {**with_approval(REQ), "lib/a.py": b"x", TEST: _t(TAG)}
    repo = FakeRepo(base, head, {"src/a.py": "lib/a.py"})
    assert check_k(repo, repo.changes()) == []
    no_open = FakeRepo({"src/a.py": b"x"}, head, {"src/a.py": "lib/a.py"})
    assert _rules(check_k(no_open, no_open.changes())) == ["K.a"]


def _d(
    base: dict[str, bytes], head: dict[str, bytes], renames: dict[str, str] | None = None
) -> list[Finding]:
    repo = FakeRepo(base, head, renames)
    return check_d(repo, repo.changes())


APPROVAL = f".specs/{REQ}/approval.json"


@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_delete_rename_parse() -> None:
    files = with_approval(REQ)
    assert _rules(_d(files, {k: v for k, v in files.items() if k != APPROVAL})) == ["D.delete"]
    moved = {
        **{k: v for k, v in files.items() if k != APPROVAL},
        f".specs/{REQ}/a2.json": files[APPROVAL],
    }
    assert "D.delete" in _rules(_d(files, moved, {APPROVAL: f".specs/{REQ}/a2.json"}))
    assert _rules(_d({}, {APPROVAL: b"{"})) == ["D.parse"]


@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_open() -> None:
    assert _d({}, with_approval(REQ)) == []
    missing = {k: v for k, v in with_approval(REQ).items() if not k.endswith("04_unit_tests.md")}
    assert "D.a" in _rules(_d({}, missing))
    empty = {**with_approval(REQ), f".specs/{REQ}/04_unit_tests.md": b""}
    rules = _rules(_d({}, empty))
    assert "D.a" in rules
    assert "D.b" in rules
    extra = {**with_approval(REQ), f".specs/{REQ}/05_x.md": b"x"}
    assert _rules(_d({}, extra)) == ["D.b"]


def _closed(tests: dict[str, bytes], spec: str = f"- **[{TAG}] x**\n") -> dict[str, bytes]:
    return {**with_approval(REQ, "closed", spec), **tests}


@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_closed() -> None:
    assert _d({}, _closed({TEST: _t(TAG)})) == []
    assert _rules(_d({}, _closed({}))) == ["D.c"]
    two = f"- **[{TAG}] x**\n- **[REQ-2026-010-F02] y**\n"
    assert _rules(_d({}, _closed({}, two))) == ["D.c", "D.c"]
    assert _d({}, _closed({}, "no tags\n")) == []
    assert _d({}, _closed({TEST: _t(TAG), "tests/test_bad.py": b"def ("})) == []
    no_spec = {k: v for k, v in _closed({}).items() if not k.endswith("01_req_spec.md")}
    assert "D.c" in _rules(_d({}, no_spec))


@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_closed_unreadable_spec() -> None:
    files = {**design_files(REQ), f".specs/{REQ}/01_req_spec.md": b"\xff"}
    guarded = {p.rsplit("/", 1)[1]: b for p, b in files.items()}
    files[APPROVAL] = approval_json(REQ, "closed", guarded)
    assert _rules(_d({}, files)) == ["D.c"]


@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_withdrawn() -> None:
    assert _d({}, {APPROVAL: approval_json(REQ, "withdrawn", {})}) == []


@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_d() -> None:
    one = with_approval(REQ)
    two = {**one, **with_approval("REQ-2026-011")}
    assert "D.d" not in _rules(_d({}, one))
    assert "D.d" in _rules(_d(one, two))
    assert _d(two, {**two, "docs/x.md": b"x"}) == []


def _t_check(files: dict[str, bytes]) -> list[Finding]:
    repo = FakeRepo({}, files)
    return check_t(repo, [])


SPEC = {f".specs/{REQ}/01_req_spec.md": f"- **[{TAG}] x**\n".encode()}


@pytest.mark.requirement("REQ-2026-010-F03")
def test_t_a() -> None:
    assert _t_check({**SPEC, TEST: _t(TAG)}) == []
    cases = {
        "def test_a(): pass": "marker",
        "@pytest.mark.requirement(V)\ndef test_a(): pass": "リテラル",
        '@pytest.mark.requirement("bad")\ndef test_a(): pass': "bad",
        "def (": "解析",
    }
    for src, word in cases.items():
        findings = _t_check({**SPEC, TEST: src.encode()})
        assert _rules(findings) == ["T.a"]
        assert word in findings[0].message or word == "marker"
    mixed = (
        f'@pytest.mark.requirement("{TAG}")\n@pytest.mark.requirement("bad")\ndef test_a(): pass\n'
    )
    assert _rules(_t_check({**SPEC, TEST: mixed.encode()})) == ["T.a"]


@pytest.mark.requirement("REQ-2026-010-F03")
def test_t_b() -> None:
    assert _rules(_t_check({TEST: _t(TAG)})) == ["T.b"]
    assert _rules(_t_check({**SPEC, TEST: _t("REQ-2026-010-F02")})) == ["T.b"]


@pytest.mark.requirement("REQ-2026-010-F03")
def test_t_c() -> None:
    assert _rules(_t_check({"src/test_x.py": b"", "tests/conftest.py": b"", "x_test.py": b""})) == [
        "T.c"
    ]


def _pragma(
    base: dict[str, bytes], head: dict[str, bytes], renames: dict[str, str] | None = None
) -> list[Finding]:
    repo = FakeRepo(base, head, renames)
    return check_pragma(repo, repo.changes())


PRAGMA = b"x = 1\nif y:  # pragma: no cover\n    z = 2\n"


@pytest.mark.requirement("REQ-2026-010-F04")
def test_pragma_new_and_kept() -> None:
    found = _pragma({"src/a.py": b"x = 1\n"}, {"src/a.py": PRAGMA})
    assert [(f.rule, f.path) for f in found] == [("Q.pragma", "src/a.py:2")]
    assert _pragma({"src/a.py": PRAGMA}, {"src/a.py": PRAGMA + b"w = 1\n"}) == []
    assert _pragma({}, {"src/new.py": PRAGMA})[0].path == "src/new.py:2"


@pytest.mark.requirement("REQ-2026-010-F04")
def test_pragma_moves_are_not_additions() -> None:
    assert _pragma({"src/a.py": PRAGMA}, {"src/b.py": PRAGMA}, {"src/a.py": "src/b.py"}) == []
    assert _pragma({"src/a.py": PRAGMA}, {"src/b.py": PRAGMA}) == []
    both = {"src/a.py": b"x\n", "src/b.py": PRAGMA}
    assert _pragma({"src/a.py": PRAGMA}, both) == []


@pytest.mark.requirement("REQ-2026-010-F04")
def test_pragma_duplicates_and_ignored_files() -> None:
    twice = PRAGMA + b"if y:  # pragma: no cover\n    z = 2\n"
    found = _pragma({"src/a.py": PRAGMA}, {"src/a.py": twice.replace(b"if y:  #", b"if y:  #")})
    assert len(found) == 1
    assert _pragma({}, {"lib/a.py": PRAGMA, "src/a.txt": PRAGMA}) == []
    assert _pragma({"src/a.py": b"\xff"}, {"src/a.py": b"\xff# pragma: no cover"}) == []


@pytest.mark.requirement("REQ-2026-010-F07")
def test_human_merge() -> None:
    changes = [
        Change(None, "scripts/gate.sh", "added"),
        Change("scripts/gate.sh", "scripts/gate.sh", "modified"),
        Change(None, ".specs/REQ-2026-010/approval.json", "added"),
        Change(None, "docs/x.md", "added"),
    ]
    assert human_merge(changes) == ("scripts/**", "決定(approval.json)")
    assert human_merge([Change(None, "docs/x.md", "added")]) == ()


@pytest.mark.requirement("REQ-2026-010-F01")
def test_run_all_collects_every_check() -> None:
    base = {**with_approval(REQ), "src/a.py": b"x\n"}
    head = {
        **base,
        "src/a.py": PRAGMA,
        "tests/test_x.py": b"def test_a(): pass\n",
        "scripts/gate.sh": b"x",
        f".specs/{REQ}/approval.json": b"{",
    }
    result = run_all(FakeRepo(base, head))
    assert {f.rule for f in result.findings} >= {"K.b", "D.parse", "T.a", "Q.pragma"}
    assert "scripts/**" in result.human_merge
    assert not result.ok


@pytest.mark.requirement("REQ-2026-010-F01")
def test_run_all_propagates_repo_error() -> None:
    class Broken(FakeRepo):
        def changes(self) -> list[Change]:
            msg = "boom"
            raise RepoError(msg)

    with pytest.raises(RepoError):
        run_all(Broken({}, {}))
