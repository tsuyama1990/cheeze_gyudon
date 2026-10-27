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
    assert _rules(_k({}, {TEST: _t(TAG)})) == ["K.a"]
    assert _rules(_k({TEST: _t(TAG)}, {TEST: _t(TAG, "pass  # edited")})) == ["K.a"]
    assert _rules(_k({}, {"src/a.py": b"x", TEST: _t(TAG)})) == ["K.a"]
    assert _rules(_k({}, {"src/a.py": b"x", ".specs/x/y.md": b"x"})) == ["K.a"]


@pytest.mark.spec("L3-U21")
@pytest.mark.requirement("REQ-2026-010-F01")
def test_k_a_counts_valid_opens() -> None:
    base = with_approval(REQ)
    head = {**base, "src/a.py": b"x", TEST: _t(TAG)}
    assert _k(base, head) == []
    two = {**base, **with_approval("REQ-2026-011")}
    assert _rules(_k(two, {**two, "src/a.py": b"x", TEST: _t(TAG)})) == ["K.a"]


@pytest.mark.spec("L2-I18", "L3-U22")
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


@pytest.mark.spec("L2-I18", "L3-U22")
@pytest.mark.requirement("REQ-2026-010-F01")
def test_k_b_rename() -> None:
    base = {**with_approval(REQ), "src/a.py": b"x"}
    head = {k: v for k, v in base.items() if k != f".specs/{REQ}/02_system_design.md"}
    head[f".specs/{REQ}/notes.md"] = base[f".specs/{REQ}/02_system_design.md"]
    repo = FakeRepo(base, head, {f".specs/{REQ}/02_system_design.md": f".specs/{REQ}/notes.md"})
    repo2 = FakeRepo(base, {**head, "src/a.py": b"y"}, repo._renames)  # noqa: SLF001
    assert "K.b" in _rules(check_k(repo2, repo2.changes()))


@pytest.mark.spec("L2-I19", "L3-U23")
@pytest.mark.requirement("REQ-2026-010-F01")
def test_k_c() -> None:
    base = with_approval(REQ)
    src = {"src/a.py": b"x"}
    assert "K.c" in _rules(_k(base, {**base, **src, "tests/test_o.py": _t("REQ-2026-001-F01")}))
    assert "K.c" in _rules(_k(base, {**base, **src, f".specs/{OTHER}/x.md": b"x"}))
    removed = {**base, "tests/test_o.py": _t("REQ-2026-001-F01")}
    assert "K.c" in _rules(_k(removed, {**base, **src}))
    assert _k(base, {**base, **src, TEST: _t(TAG)}) == []


@pytest.mark.spec("L3-U24")
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


@pytest.mark.spec("L3-U25", "L2-I20")
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


@pytest.mark.spec("L2-I20")
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


@pytest.mark.spec("L3-U27", "L2-I20")
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


@pytest.mark.spec("L3-U28", "L3-U29", "L2-I20")
@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_withdrawn() -> None:
    assert _d({}, {APPROVAL: approval_json(REQ, "withdrawn", {})}) == []


@pytest.mark.spec("L3-U29", "L2-I21")
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


@pytest.mark.spec("L2-I22", "L3-U30")
@pytest.mark.requirement("REQ-2026-010-F03")
def test_t_a() -> None:
    assert _t_check({**SPEC, TEST: _t(TAG)}) == []
    cases = {
        "def test_a(): pass": "requirement marker がない",
        "@pytest.mark.requirement(V)\ndef test_a(): pass": "リテラルでない引数",
        '@pytest.mark.requirement("bad")\ndef test_a(): pass': "形式不正のタグ: bad",
        "def (": "解析できない",
    }
    for src, message in cases.items():
        findings = _t_check({**SPEC, TEST: src.encode()})
        assert _rules(findings) == ["T.a"]
        assert message in findings[0].message
    mixed = (
        f'@pytest.mark.requirement("{TAG}")\n@pytest.mark.requirement("bad")\ndef test_a(): pass\n'
    )
    mixed_findings = _t_check({**SPEC, TEST: mixed.encode()})
    assert _rules(mixed_findings) == ["T.a"]
    assert "形式不正のタグ: bad" in mixed_findings[0].message


@pytest.mark.spec("L2-I22", "L3-U31")
@pytest.mark.requirement("REQ-2026-010-F03")
def test_t_b() -> None:
    assert _rules(_t_check({TEST: _t(TAG)})) == ["T.b"]
    assert _rules(_t_check({**SPEC, TEST: _t("REQ-2026-010-F02")})) == ["T.b"]


@pytest.mark.spec("L2-I22", "L3-U32")
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


@pytest.mark.spec("L3-U33", "L2-I48")
@pytest.mark.requirement("REQ-2026-010-F04")
def test_pragma_new_and_kept() -> None:
    found = _pragma({"src/a.py": b"x = 1\n"}, {"src/a.py": PRAGMA})
    assert [(f.rule, f.path) for f in found] == [("Q.pragma", "src/a.py:2")]
    assert _pragma({"src/a.py": PRAGMA}, {"src/a.py": PRAGMA + b"w = 1\n"}) == []
    assert _pragma({}, {"src/new.py": PRAGMA})[0].path == "src/new.py:2"


@pytest.mark.spec("L3-U33", "L2-I48")
@pytest.mark.requirement("REQ-2026-010-F04")
def test_pragma_moves_are_not_additions() -> None:
    assert _pragma({"src/a.py": PRAGMA}, {"src/b.py": PRAGMA}, {"src/a.py": "src/b.py"}) == []
    assert _pragma({"src/a.py": PRAGMA}, {"src/b.py": PRAGMA}) == []
    both = {"src/a.py": b"x\n", "src/b.py": PRAGMA}
    assert _pragma({"src/a.py": PRAGMA}, both) == []


@pytest.mark.spec("L3-U33", "L2-I48")
@pytest.mark.requirement("REQ-2026-010-F04")
def test_pragma_duplicates_and_ignored_files() -> None:
    twice = PRAGMA + b"if y:  # pragma: no cover\n    z = 2\n"
    found = _pragma({"src/a.py": PRAGMA}, {"src/a.py": twice.replace(b"if y:  #", b"if y:  #")})
    assert len(found) == 1
    assert _pragma({}, {"lib/a.py": PRAGMA, "src/a.txt": PRAGMA}) == []
    assert _pragma({"src/a.py": b"\xff"}, {"src/a.py": b"\xff# pragma: no cover"}) == []


@pytest.mark.spec("L2-I23", "L3-U34")
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


@pytest.mark.spec("L2-I24", "L3-U35")
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


@pytest.mark.spec("L3-U36")
@pytest.mark.requirement("REQ-2026-010-F01")
def test_run_all_propagates_repo_error() -> None:
    class Broken(FakeRepo):
        def changes(self) -> list[Change]:
            msg = "boom"
            raise RepoError(msg)

    with pytest.raises(RepoError):
        run_all(Broken({}, {}))


@pytest.mark.requirement("REQ-2026-010-F01")
def test_k_on_tests_only_pr() -> None:
    approved = with_approval(REQ)
    new_test = {TEST: _t(TAG)}
    assert _rules(_k(approved, {**approved, **new_test})) == []
    assert _rules(_k({}, new_test)) == ["K.a"]
    other = {TEST: _t("REQ-2026-001-F01")}
    assert _rules(_k(approved, {**approved, **other})) == ["K.c"]
    edited = {**approved, TEST: _t(TAG, "assert 1")}
    assert _rules(_k({**approved, **new_test}, edited)) == []
    assert _rules(_k({**new_test}, {TEST: _t(TAG, "assert 1")})) == ["K.a"]
    renamed = {TEST: _t(TAG).replace(b"test_a", b"test_renamed")}
    assert _rules(_k(new_test, renamed)) == ["K.a"]


@pytest.mark.spec("L2-I52")
@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_completing_an_open_requirement() -> None:
    spec = f"- **[{TAG}] x**\n- **[REQ-2026-010-F02] y**\n"
    open_ = {**with_approval(REQ, spec=spec), TEST: _t(TAG)}
    closed = with_approval(REQ, "closed", spec)
    untested = _d(open_, {**closed, TEST: _t(TAG)})
    assert [f.message for f in untested] == ["REQ-2026-010-F02 にテストがない"]
    shrunk_spec = f"- **[{TAG}] x**\n"
    dropped = {**with_approval(REQ, "closed", shrunk_spec), TEST: _t(TAG)}
    findings = _d(open_, dropped)
    assert {f.path for f in findings} >= {f".specs/{REQ}/01_req_spec.md"}
    assert {f.rule for f in findings} == {"D.c"}
    tampered = {**closed, f".specs/{REQ}/02_system_design.md": b"changed", TEST: _t(TAG)}
    assert [f.path for f in _d(open_, tampered)] == [
        f".specs/{REQ}/02_system_design.md",
        f".specs/{REQ}",
    ]
    done = {
        **with_approval(REQ, spec=f"- **[{TAG}] x**\n"),
        TEST: _t(TAG),
    }
    finished = {**with_approval(REQ, "closed", f"- **[{TAG}] x**\n"), TEST: _t(TAG)}
    assert _d(done, finished) == []
    assert _d({}, finished) == []


@pytest.mark.spec("L2-I52")
@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_closing_needs_a_valid_open_approval() -> None:
    """L3-U50"""
    spec = f"- **[{TAG}] x**\n"
    tested = {TEST: _t(TAG)}
    closed = {**with_approval(REQ, "closed", spec), **tested}
    stale = {
        **with_approval(REQ, spec=spec),
        f".specs/{REQ}/01_req_spec.md": b"- **[REQ-2026-010-F09] y**\n",
    }
    assert [f.message for f in _d({**stale, **tested}, closed)] == [
        "承認が失効している(更新してから閉じる)"
    ]
    withdrawn = {**with_approval(REQ, "withdrawn"), **tested}
    assert [f.rule for f in _d(withdrawn, closed)] == ["D.c"]
    already_closed = {**with_approval(REQ, "closed", spec), **tested}
    assert _d(already_closed, {**closed, "README.md": b"x"}) == []
    no_approval = {f".specs/{REQ}/01_req_spec.md": spec.encode(), **tested}
    assert _d(no_approval, closed) == []


@pytest.mark.requirement("REQ-2026-010-F03")
def test_t_flags_a_dynamic_marker_even_next_to_a_literal_one() -> None:
    """L3-U30"""
    spec = f"- **[{TAG}] x**\n"
    source = (
        b"import pytest\n\npytestmark = pytest.mark.requirement("
        + f'"{TAG}"'.encode()
        + b")\n\n\n@pytest.mark.requirement(OTHER)\ndef test_a():\n    pass\n"
    )
    findings = _t_check({**with_approval(REQ, spec=spec), TEST: source})
    assert [(f.rule, f.message) for f in findings] == [
        ("T.a", "リテラルでない引数の requirement marker がある")
    ]


@pytest.mark.requirement("REQ-2026-010-F02")
def test_d_closing_protects_files_under_numbered_directories() -> None:
    """L3-U50"""
    spec = f"- **[{TAG}] x**\n"
    nested = f".specs/{REQ}/05_evidence/note.md"
    base = {**with_approval(REQ, spec=spec), nested: b"a", TEST: _t(TAG)}
    head = {**with_approval(REQ, "closed", spec), nested: b"b", TEST: _t(TAG)}
    assert [f.path for f in _d(base, head)] == [nested]


@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.spec("L3-U51", "L2-I51")
def test_k_on_changed_tests_with_an_approval() -> None:
    approved = with_approval(REQ)
    base = {**approved, TEST: _t(TAG)}
    rewritten = {**approved, TEST: _t(TAG, "assert 1")}
    other_req = {**approved, TEST: _t("REQ-2026-001-F01", "assert 1")}
    renamed_in = {**approved, TEST: _t(TAG).replace(b"test_a", b"test_b")}
    renamed_out = {**approved, TEST: _t("REQ-2026-001-F01").replace(b"test_a", b"test_b")}
    assert _k(base, rewritten) == []
    assert _rules(_k(base, other_req)) == ["K.c"]
    assert _k(base, renamed_in) == []
    assert _rules(_k(base, renamed_out)) == ["K.c"]
    moved = FakeRepo(base, {**approved, "tests/test_y.py": _t(TAG)}, {TEST: "tests/test_y.py"})
    assert check_k(moved, moved.changes()) == []
    no_approval = FakeRepo({TEST: _t(TAG)}, {"tests/test_y.py": _t(TAG)}, {TEST: "tests/test_y.py"})
    assert check_k(no_approval, no_approval.changes()) == []


@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.spec("L3-U20", "L2-I17")
@pytest.mark.parametrize("opens", [0, 1, 2])
@pytest.mark.parametrize("src", [False, True])
@pytest.mark.parametrize("aux", [False, True])
@pytest.mark.parametrize("fn", [False, True])
def test_k_truth_table(*, opens: int, src: bool, aux: bool, fn: bool) -> None:
    base: dict[str, bytes] = {}
    for i in range(opens):
        base.update(
            with_approval(f"REQ-2026-0{10 + i}", spec=f"- **[REQ-2026-0{10 + i}-F01] x**\n")
        )
    head = dict(base)
    if src:
        head["src/a.py"] = b"x = 1\n"
    if aux:
        head["docs_unused"] = b""
        head[".specs/REQ-2026-099/notes.txt"] = b"n"
    if fn:
        head[TEST] = _t("REQ-2026-010-F01")
    applies = (src and (aux or fn)) or fn
    findings = _k(base, head)
    if not applies:
        assert findings == []
    elif opens != 1:
        assert _rules(findings)[:1] == ["K.a"]
    else:
        assert "K.a" not in _rules(findings)


@pytest.mark.requirement("REQ-2026-010-F02")
@pytest.mark.spec("L3-U26", "L2-I20")
def test_d_open_missing_files_are_reported_per_file() -> None:
    full = with_approval(REQ)
    only_design = {k: v for k, v in full.items() if not k.endswith("02_system_tests.md")}
    only_spec = {k: v for k, v in full.items() if not k.endswith("02_system_design.md")}
    assert [f.path for f in _d({}, only_design) if f.rule == "D.a"] == [
        f".specs/{REQ}/02_system_tests.md"
    ]
    assert [f.path for f in _d({}, only_spec) if f.rule == "D.a"] == [
        f".specs/{REQ}/02_system_design.md"
    ]
    both = {
        k: v
        for k, v in full.items()
        if not k.endswith(("02_system_tests.md", "03_architecture.md", "04_unit_tests.md"))
    }
    assert len([f for f in _d({}, both) if f.rule == "D.a"]) == 3
    hash_only = {**full, f".specs/{REQ}/03_architecture.md": b"changed"}
    assert _rules(_d({}, hash_only)) == ["D.b"]


@pytest.mark.requirement("REQ-2026-010-F02")
@pytest.mark.spec("L2-I21")
def test_d_d_counts_open_approvals_in_head() -> None:
    one = with_approval(REQ)
    stale = {**with_approval("REQ-2026-011"), ".specs/REQ-2026-011/01_req_spec.md": b"changed"}
    assert "D.d" in _rules(_d(one, {**one, **stale}))
    closed_edit = {**with_approval("REQ-2026-011", "closed"), **with_approval(REQ)}
    still_open = {**one, **with_approval("REQ-2026-011", "open")}
    assert "D.d" in _rules(_d({**one, **with_approval("REQ-2026-011", "closed")}, still_open))
    assert "D.d" not in _rules(_d({}, closed_edit))
