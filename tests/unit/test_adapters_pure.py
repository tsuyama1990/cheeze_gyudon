import json
from collections.abc import Callable

import pytest

from jtc_gov.adapters.cli import run_check
from jtc_gov.adapters.report import findings_json, format_findings, format_status, short_status
from jtc_gov.domain.errors import RepoError
from jtc_gov.domain.models import CheckResult, Finding
from jtc_gov.domain.repo import Repo
from tests.support.fake_repo import FakeRepo, with_approval

REQ = "REQ-2026-010"


@pytest.mark.spec("L2-I26", "L3-U43")
@pytest.mark.requirement("REQ-2026-010-F07")
def test_format_findings() -> None:
    assert format_findings(CheckResult((), ())) == ""
    result = CheckResult(
        (Finding("K.b", "a/b", "msg"), Finding("D.d", None, "two opens")),
        ("scripts/**", "AGENT.md"),
    )
    assert format_findings(result).splitlines() == [
        "K.b a/b: msg",
        "D.d: two opens",
        "人間のマージが必要: scripts/**, AGENT.md",
    ]


@pytest.mark.spec("L2-I26", "L3-U44")
@pytest.mark.requirement("REQ-2026-010-F07")
def test_findings_json() -> None:
    empty = json.loads(findings_json(CheckResult((), ())))
    assert empty == {"ok": True, "findings": [], "human_merge": []}
    full = json.loads(findings_json(CheckResult((Finding("K.a", None, "m", "h"),), ("x",))))
    assert full["ok"] is False
    assert full["findings"] == [{"rule": "K.a", "path": None, "message": "m", "hint": "h"}]
    assert full["human_merge"] == ["x"]


def _repo(*approvals: tuple[str, str]) -> FakeRepo:
    files: dict[str, bytes] = {}
    for req, state in approvals:
        files.update(with_approval(req, state))
    return FakeRepo(files, files)


@pytest.mark.spec("L3-U45")
@pytest.mark.requirement("REQ-2026-010-F06")
def test_status_no_requirements() -> None:
    out = format_status(_repo(), "worktree")
    assert "要件なし" in out
    assert "不可 (有効な open な承認が 0 個)" in out
    assert len(short_status(_repo()).splitlines()) <= 3


@pytest.mark.spec("L3-U45")
@pytest.mark.requirement("REQ-2026-010-F06")
def test_status_one_open_and_two_opens() -> None:
    one = _repo((REQ, "open"))
    assert f"{REQ}: open / 有効 / ゲート 5" in format_status(one, "HEAD")
    assert f"可能 ({REQ})" in format_status(one, "HEAD")
    two = _repo((REQ, "open"), ("REQ-2026-011", "open"))
    assert "不可 (有効な open な承認が 2 個)" in format_status(two, "HEAD")


@pytest.mark.spec("L3-U45")
@pytest.mark.requirement("REQ-2026-010-F06")
def test_status_invalid_and_broken_approvals() -> None:
    files = with_approval(REQ)
    files[f".specs/{REQ}/05_x.md"] = b"x"
    files[".specs/REQ-2026-011/approval.json"] = b"{"
    repo = FakeRepo({}, files)
    out = format_status(repo, "x")
    assert "失効" in out
    assert "set: extra: 05_x.md" in out
    assert "承認ファイルが読めない" in out
    short = short_status(repo)
    assert len(short.splitlines()) <= 3
    assert REQ in short
    assert "REQ-2026-011" in short


def _opener(repo: Repo | Exception) -> Callable[[], Repo]:
    def open_repo() -> Repo:
        if isinstance(repo, Exception):
            raise repo
        return repo

    return open_repo


@pytest.mark.spec("L3-U48")
@pytest.mark.requirement("REQ-2026-010-F01")
def test_run_check_exit_codes() -> None:
    clean = FakeRepo({}, {})
    assert run_check(_opener(clean), as_json=False) == (0, "")
    violation = FakeRepo({}, {"src/a.py": b"x", "tests/test_x.py": b"def test_a(): pass\n"})
    code, out = run_check(_opener(violation), as_json=False)
    assert code == 1
    assert "K.a" in out


@pytest.mark.spec("L3-U48")
@pytest.mark.requirement("REQ-2026-010-F01")
def test_run_check_unevaluated() -> None:
    code, out = run_check(_opener(RepoError("no base")), as_json=False)
    assert (code, out) == (2, "E.repo: no base")
    code, out = run_check(_opener(RuntimeError("bug")), as_json=False)
    assert code == 2
    assert "E.internal" in out
    assert "Traceback" not in out
    _, debug_out = run_check(_opener(RuntimeError("bug")), as_json=False, debug=True)
    assert "Traceback" in debug_out
    _, js = run_check(_opener(RepoError("x")), as_json=True)
    assert json.loads(js)["findings"][0]["rule"] == "E.repo"


@pytest.mark.requirement("REQ-2026-010-F06")
def test_status_of_a_closed_requirement_is_not_reported_as_invalid() -> None:
    files = with_approval("REQ-2026-010", "closed")
    text = format_status(FakeRepo(files, files), "worktree")
    assert "REQ-2026-010: closed / ゲート 5" in text
    assert "失効" not in text


@pytest.mark.spec("L3-U52")
@pytest.mark.requirement("REQ-2026-010-F06")
def test_src_change_allowed_follows_base_not_head() -> None:
    closed_on_base = with_approval(REQ, "closed")
    reopened_on_head = with_approval(REQ, "open")
    repo = FakeRepo(closed_on_base, reopened_on_head)
    assert "不可" in format_status(repo, "worktree")
    assert "不可" in short_status(repo)
