import json
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

import pytest
from click.testing import CliRunner

from jtc_gov.adapters.cli import main
from jtc_gov.domain.gates import DELIVERABLES
from tests.integration.test_repo_git import commit, git, root  # noqa: F401
from tests.support.fake_repo import approval_json, design_files, with_approval
from tests.support.paths import MACHINERY_PATHS

Files = Mapping[str, bytes]


class Scenario(NamedTuple):
    base: Files
    head: Files
    code: int
    text: str


REQ = "REQ-2026-010"
OTHER = "REQ-2026-011"
SPEC2 = "- **[REQ-2026-010-F01] a**\n- **[REQ-2026-010-F02] b**\n"
SPEC_OTHER = "- **[REQ-2026-011-F01] z**\n"
HUMAN = "人間のマージが必要"
README: dict[str, bytes] = {"README.md": b"readme\n"}
SRC: dict[str, bytes] = {"src/a.py": b"x = 1\n"}
SRC_EDIT: dict[str, bytes] = {"src/a.py": b"x = 2\n"}


def make_test_file(tag: str, location: str = "tests/test_a.py") -> dict[str, bytes]:
    body = (
        f'import pytest\n\n\n@pytest.mark.requirement("{tag}")\ndef test_a() -> None:\n    pass\n'
    )
    return {location: body.encode()}


TEST = make_test_file("REQ-2026-010-F01")
TEST_RENAMED = {
    "tests/test_a.py": make_test_file("REQ-2026-010-F01")["tests/test_a.py"].replace(
        b"test_a", b"test_renamed"
    )
}
TEST_EDIT = {"tests/test_a.py": TEST["tests/test_a.py"] + b"# edited\n"}
TEST_BODY = {"tests/test_a.py": TEST["tests/test_a.py"].replace(b"pass", b"assert True")}
APPROVED = {**README, **with_approval(REQ)}
SPEC_PATH = f".specs/{REQ}/01_req_spec.md"
APPROVAL_PATH = f".specs/{REQ}/approval.json"


def run(repo: Path, scenario: Scenario, monkeypatch: pytest.MonkeyPatch) -> None:
    base_sha = commit(repo, scenario.base)
    commit(repo, scenario.head)
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(main, ["check", "--base", base_sha, "--head", "HEAD"])
    assert result.exit_code == scenario.code, result.output
    assert scenario.text in result.output


def closed_with_tests(req: str = REQ) -> dict[str, bytes]:
    return {**with_approval(req, "closed"), **make_test_file(f"{req}-F01")}


def rule_cases() -> list[object]:
    stale_spec = {**APPROVED, SPEC_PATH: (SPEC2).encode()}
    two_open = {**APPROVED, **with_approval(OTHER, spec=SPEC_OTHER)}
    spec_edit = {**APPROVED, SPEC_PATH: b"- **[REQ-2026-010-F01] x**\nedited\n"}
    set_changed = {**APPROVED, f".specs/{REQ}/05_notes.md": b"n"}
    big_src = {"src/a.py": b"line\n" * 40}
    closed_base = {**README, **with_approval(REQ, "closed"), **TEST}
    approved_base = {**README, **with_approval(REQ), **TEST}
    cases = [
        ("L1-E01", README, {**README, **SRC, **TEST}, 1, "K.a"),
        ("L1-E46", README, {**README, **TEST}, 1, "K.a"),
        ("L1-E46-approved", APPROVED, {**APPROVED, **TEST}, 0, ""),
        ("L1-E46-body-rewrite", closed_base, {**closed_base, **TEST_BODY}, 1, "K.a"),
        ("L1-E46-function-rename", closed_base, {**closed_base, **TEST_RENAMED}, 1, "K.a"),
        ("L1-E46-body-rewrite-approved", approved_base, {**approved_base, **TEST_BODY}, 0, ""),
        ("L1-E02", APPROVED, {**APPROVED, **SRC, **TEST}, 0, ""),
        ("L1-E03", stale_spec, {**stale_spec, **SRC, **TEST}, 1, "K.a"),
        (
            "L1-E04",
            {**README, **closed_with_tests()},
            {**README, **closed_with_tests(), **SRC, **TEST_EDIT},
            1,
            "K.a",
        ),
        ("L1-E05", two_open, {**two_open, **SRC, **TEST}, 1, "K.a"),
        (
            "L1-E07",
            {**README, **big_src},
            {**README, "lib/a.py": big_src["src/a.py"], **TEST},
            1,
            "K.a",
        ),
        (
            "L1-E08",
            APPROVED,
            {**APPROVED, **SRC, **TEST, SPEC_PATH: spec_edit[SPEC_PATH]},
            1,
            "K.b",
        ),
        (
            "L1-E09",
            APPROVED,
            {
                **APPROVED,
                **SRC,
                f".specs/{OTHER}/01_req_spec.md": SPEC_OTHER.encode(),
                **make_test_file("REQ-2026-011-F01"),
            },
            1,
            "K.c",
        ),
        ("L1-E10", set_changed, {**set_changed, **SRC, **TEST}, 1, "K.a"),
        ("L1-E30", {**README, **SRC}, {**README, **SRC_EDIT}, 0, ""),
        ("L1-E34", {**README, **SRC}, {**README, **SRC_EDIT, **TEST}, 1, "K.a"),
        ("L1-E36", README, {**README, "pyproject.toml": b"[x]\n"}, 0, HUMAN),
    ]
    return [pytest.param(Scenario(b, h, code, text), id=name) for name, b, h, code, text in cases]


@pytest.mark.spec("L1-E35")
@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.parametrize("scenario", rule_cases())
def test_k_scenarios(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    scenario: Scenario,
) -> None:
    run(root, scenario, monkeypatch)


def d_cases() -> list[object]:
    no_unit = design_files(REQ)
    del no_unit[f".specs/{REQ}/04_unit_tests.md"]
    missing = {
        **no_unit,
        APPROVAL_PATH: approval_json(
            REQ, "open", {p.rsplit("/", 1)[1]: b for p, b in no_unit.items()}
        ),
    }
    tampered = {**with_approval(REQ), f".specs/{REQ}/02_system_design.md": b"tampered"}
    legacy = {
        ".specs/REQ-2026-001/01_req_spec.md": b"legacy\n",
        ".specs/REQ-2026-001/approval.json": approval_json("REQ-2026-001", "closed", {}),
    }
    untested = with_approval(REQ, "closed", SPEC2) | make_test_file("REQ-2026-010-F01")
    withdrawn = {**with_approval(REQ), APPROVAL_PATH: approval_json(REQ, "withdrawn", {})}
    swap_base = {
        **with_approval(REQ, "closed") | make_test_file("REQ-2026-010-F01"),
        **design_files(OTHER, SPEC_OTHER),
    }
    swap_head = {**swap_base, **with_approval(OTHER, "open", SPEC_OTHER)}
    second_open = {**APPROVED, **with_approval(OTHER, spec=SPEC_OTHER)}
    stale_open = {
        **README,
        **with_approval(REQ, spec=SPEC2),
        SPEC_PATH: b"- **[REQ-2026-010-F01] a**\n",
        **TEST,
    }
    stale_closed = {**stale_open, APPROVAL_PATH: with_approval(REQ, "closed")[APPROVAL_PATH]}
    withdrawn_base = {**README, **with_approval(REQ, "withdrawn"), **TEST}
    withdrawn_then_closed = {**withdrawn_base, **with_approval(REQ, "closed"), **TEST}
    spec2_open = {**README, **with_approval(REQ, spec=SPEC2), **TEST}
    tag_removed = {**README, **with_approval(REQ, "closed"), **TEST}
    tampered_close = {
        **README,
        **with_approval(REQ, "closed", SPEC2),
        f".specs/{REQ}/02_system_design.md": b"changed",
        **TEST,
    }
    without_approval = {k: v for k, v in APPROVED.items() if k != APPROVAL_PATH}
    cases = [
        ("L1-E06", APPROVED, second_open, 1, "D.d"),
        ("L1-E11", README, {**README, **missing}, 1, "04_unit_tests.md"),
        ("L1-E12", README, {**README, **tampered}, 1, "D.b"),
        ("L1-E13", README, {**README, **with_approval(REQ)}, 0, HUMAN),
        (
            "L1-E14",
            APPROVED | make_test_file("REQ-2026-010-F01"),
            {
                **README,
                **untested,
                SPEC_PATH: SPEC2.encode(),
                APPROVAL_PATH: approval_json(
                    REQ,
                    "closed",
                    {p.rsplit("/", 1)[1]: b for p, b in design_files(REQ, SPEC2).items()},
                ),
            },
            1,
            "D.c",
        ),
        (
            "L1-E15",
            {**README, **with_approval(REQ), **TEST},
            {**README, **closed_with_tests()},
            0,
            HUMAN,
        ),
        ("L1-E16", README, {**README, **legacy}, 0, ""),
        ("L1-E17", APPROVED, {**README, **withdrawn}, 0, ""),
        (
            "L1-E17-then-open-another",
            {**README, **withdrawn},
            {**README, **withdrawn, **with_approval(OTHER, spec=SPEC_OTHER)},
            0,
            "",
        ),
        ("L1-E18", APPROVED, without_approval, 1, "D.delete"),
        ("L1-E47-tag-removed", spec2_open, tag_removed, 1, "D.c"),
        ("L1-E47-stale-approval", stale_open, stale_closed, 1, "D.c"),
        ("L1-E47-via-withdrawn", withdrawn_base, withdrawn_then_closed, 1, "D.c"),
        ("L1-E47-design-tampered", spec2_open, tampered_close, 1, "D.c"),
        (
            "L1-E19",
            swap_base,
            swap_head | {f".specs/{REQ}/approval.json": swap_base[APPROVAL_PATH]},
            0,
            "",
        ),
    ]
    return [pytest.param(Scenario(b, h, code, text), id=name) for name, b, h, code, text in cases]


@pytest.mark.requirement("REQ-2026-010-F02")
@pytest.mark.parametrize("scenario", d_cases())
def test_d_scenarios(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    scenario: Scenario,
) -> None:
    run(root, scenario, monkeypatch)


def t_cases() -> list[object]:
    no_marker = {"tests/test_a.py": b"def test_a() -> None:\n    pass\n"}
    pragma = {"src/a.py": b"x = 1\ny = 2  # pragma: no cover\n"}
    docs = {"doc/x.md": b"d\n"}
    spec2 = {**README, **with_approval(REQ, spec=SPEC2)}
    cases = [
        ("L1-E20", spec2, {**spec2, **SRC, **TEST}, 0, ""),
        ("L1-E21", APPROVED, {**APPROVED, **no_marker}, 1, "T.a"),
        ("L1-E22", APPROVED, {**APPROVED, **make_test_file("REQ-INIT-001")}, 1, "T.a"),
        ("L1-E23", APPROVED, {**APPROVED, **make_test_file("REQ-2026-009-F07")}, 1, "T.b"),
        ("L1-E24", APPROVED, {**APPROVED, **make_test_file("REQ-2026-010-F09")}, 1, "T.b"),
        (
            "L1-E25",
            APPROVED,
            {**APPROVED, **make_test_file("REQ-2026-010-F01", "lib/test_x.py")},
            1,
            "T.c",
        ),
        ("L1-E27", {**APPROVED, **SRC}, {**APPROVED, **pragma}, 1, "Q.pragma"),
        ("L1-E29", README, {**README, **docs}, 0, ""),
    ]
    return [pytest.param(Scenario(b, h, code, text), id=name) for name, b, h, code, text in cases]


@pytest.mark.requirement("REQ-2026-010-F03")
@pytest.mark.parametrize("scenario", t_cases())
def test_t_and_q_scenarios(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    scenario: Scenario,
) -> None:
    run(root, scenario, monkeypatch)


@pytest.mark.spec("L1-E44")
@pytest.mark.requirement("REQ-2026-010-F07")
@pytest.mark.parametrize("path", MACHINERY_PATHS)
def test_machinery_paths_need_a_human(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    run(root, Scenario(README, {**README, path: b"# x\n"}, 0, HUMAN), monkeypatch)


@pytest.mark.requirement("REQ-2026-010-F07")
def test_json_output_lists_the_human_merge(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = commit(root, README)
    commit(root, {**README, **with_approval(REQ)})
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, ["check", "--base", base, "--head", "HEAD", "--json"])
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["human_merge"] == ["決定(approval.json)"]


@pytest.mark.spec("L1-E43")
@pytest.mark.requirement("REQ-2026-010-F06")
@pytest.mark.parametrize("pairs", [0, 1, 2, 3, 4])
def test_displayed_gate_is_the_first_incomplete_pair(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    pairs: int,
) -> None:
    present = {n for d in DELIVERABLES[:pairs] for n in (d.design, d.test_spec)}
    files = {f".specs/{REQ}/{n}": n.encode() for n in sorted(present)}
    guarded = {n: n.encode() for n in sorted(present)}
    files[APPROVAL_PATH] = approval_json(REQ, "open", guarded)
    sha = commit(root, files)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, ["status", "--base", sha, "--head", "HEAD"])
    assert result.exit_code == 0
    assert f"ゲート {pairs + 1}" in result.output


@pytest.mark.spec("L1-E43")
@pytest.mark.requirement("REQ-2026-010-F06")
def test_gate_skips_to_the_smallest_missing_pair(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keep = [DELIVERABLES[0], DELIVERABLES[2]]
    names = [n for d in keep for n in (d.design, d.test_spec)]
    files = {f".specs/{REQ}/{n}": n.encode() for n in names}
    files[APPROVAL_PATH] = approval_json(REQ, "open", {n: n.encode() for n in names})
    sha = commit(root, files)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, ["status", "--base", sha, "--head", "HEAD"])
    assert f"ゲート {DELIVERABLES[1].gate}" in result.output


@pytest.mark.requirement("REQ-2026-010-F01")
def test_full_lifecycle(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L1-E45: each step is a PR checked against the previous main."""
    monkeypatch.chdir(root)
    design = design_files(REQ, SPEC2)
    steps: list[tuple[str, dict[str, bytes], int, str]] = [
        ("requirement", {**README, SPEC_PATH: SPEC2.encode()}, 0, ""),
        ("design", {**README, **design}, 0, ""),
        ("decision", {**README, **with_approval(REQ, spec=SPEC2)}, 0, HUMAN),
        ("impl-1", {**README, **with_approval(REQ, spec=SPEC2), **SRC, **TEST}, 0, ""),
        (
            "impl-2",
            {
                **README,
                **with_approval(REQ, spec=SPEC2),
                **SRC_EDIT,
                **TEST,
                **make_test_file("REQ-2026-010-F02", "tests/test_b.py"),
            },
            0,
            "",
        ),
        (
            "edit-approved-spec",
            {
                **README,
                **with_approval(REQ, spec=SPEC2),
                **SRC,
                **TEST,
                SPEC_PATH: SPEC2.encode() + b"more\n",
            },
            1,
            "K.b",
        ),
    ]
    main_sha = commit(root, README, "init")
    for name, snapshot, code, text in steps:
        head = commit(root, snapshot, name)
        args = ["check", "--head", head, "--base", main_sha]
        result = CliRunner().invoke(main, args)
        assert result.exit_code == code, (name, result.output)
        assert text in result.output, (name, result.output)
        if code == 0:
            main_sha = head
    implemented = steps[4][1]
    closed = {**implemented, **with_approval(REQ, "closed", SPEC2)}
    head = commit(root, closed, "close")
    result = CliRunner().invoke(main, ["check", "--base", main_sha, "--head", head])
    assert result.exit_code == 0, result.output
    after = {**closed, "src/a.py": b"x = 3\n", "tests/test_c.py": TEST_EDIT["tests/test_a.py"]}
    head2 = commit(root, after, "after-close")
    late = CliRunner().invoke(main, ["check", "--base", head, "--head", head2])
    assert late.exit_code == 1
    assert "K.a" in late.output


@pytest.mark.requirement("REQ-2026-010-F01")
def test_stale_branch_is_judged_against_the_merge_base(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L1-E48: main moved on (implementation and closing); the topic only edits README."""
    monkeypatch.chdir(root)
    commit(root, APPROVED, "base")
    git(root, "checkout", "-q", "-b", "topic")
    commit(root, {**APPROVED, "README.md": b"edited\n"}, "topic")
    git(root, "checkout", "-q", "main")
    advanced = {**closed_with_tests(), **README, **SRC, **make_test_file("REQ-2026-010-F01")}
    commit(root, advanced, "main moves on")
    git(root, "checkout", "-q", "topic")
    result = CliRunner().invoke(main, ["check", "--base", "main", "--head", "HEAD"])
    assert result.exit_code == 0, result.output


@pytest.mark.requirement("REQ-2026-010-F01")
def test_stale_branch_that_adds_behavior_is_judged_on_the_latest_approval(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L1-E48: the topic adds src and tests while main has closed the requirement."""
    monkeypatch.chdir(root)
    commit(root, {**APPROVED, **TEST}, "base")
    git(root, "checkout", "-q", "-b", "topic")
    commit(root, {**APPROVED, **TEST, **SRC, **TEST_BODY}, "topic")
    git(root, "checkout", "-q", "main")
    commit(root, {**README, **closed_with_tests()}, "main closes the requirement")
    git(root, "checkout", "-q", "topic")
    result = CliRunner().invoke(main, ["check", "--base", "main", "--head", "HEAD"])
    assert result.exit_code == 1, result.output
    assert "K.a" in result.output
