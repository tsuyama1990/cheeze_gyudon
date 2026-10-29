import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.adapters.cli import main
from tests.support.guard_repos import bash, make_repos, write

APPROVAL = ".specs/REQ-X/approval.json"


def hook(stdin: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(main, ["hook", "global-guard"], input=stdin)
    return result.exit_code, result.stdout, result.stderr


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    return make_repos(tmp_path)


@pytest.mark.requirement("REQ-2026-011-F04")
def test_cwd_on_main_does_not_block_a_commit_to_a_work_branch(repos: tuple[Path, Path]) -> None:
    """L1-E08"""
    a, b = repos
    assert hook(bash(a, f"git -C {b} commit -m x")) == (0, "", "")


@pytest.mark.requirement("REQ-2026-011-F04")
def test_cwd_on_a_work_branch_does_not_hide_a_commit_to_main(repos: tuple[Path, Path]) -> None:
    """L1-E09"""
    a, b = repos
    for command in (f"git -C {a} commit -m x", f"cd {a} && git commit -m x"):
        code, _, err = hook(bash(b, command))
        assert code == 2
        assert "main" in err
        assert str(a) in err


@pytest.mark.requirement("REQ-2026-011-F04")
def test_edits_on_main_are_denied_unless_ignored(repos: tuple[Path, Path]) -> None:
    """L1-E10"""
    a, _ = repos
    (a / ".gitignore").write_text("build/\n")
    assert hook(write(a, "src/a.py"))[0] == 2
    assert hook(write(a, "build/out.txt"))[0] == 0


@pytest.mark.requirement("REQ-2026-011-F04")
def test_add_all_variants_are_denied(repos: tuple[Path, Path]) -> None:
    """L1-E11"""
    _, b = repos
    codes = [hook(bash(b, f"git add {arg}"))[0] for arg in ("-A", ".", "--all", "src/a.py")]
    assert codes == [2, 2, 2, 0]


@pytest.mark.requirement("REQ-2026-011-F05")
def test_approval_writes_ask_and_reads_pass(repos: tuple[Path, Path]) -> None:
    """L1-E12"""
    _, b = repos
    assert "ask" in hook(write(b, APPROVAL))[1]
    assert "ask" in hook(bash(b, f"echo {{}} > {APPROVAL}"))[1]
    assert hook(bash(b, f"cat {APPROVAL}")) == (0, "", "")


@pytest.mark.requirement("REQ-2026-011-F05")
def test_push_and_the_merge_script_ask(repos: tuple[Path, Path]) -> None:
    """L1-E13"""
    _, b = repos
    for command in (
        "git push",
        f"git -C {b} push origin x",
        "~/.claude/bin/merge-to-main.sh a m.md",
    ):
        code, out, _ = hook(bash(b, command))
        assert code == 0
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask"


@pytest.mark.requirement("REQ-2026-011-F05")
def test_merge_is_denied_on_main_and_allowed_on_a_work_branch(repos: tuple[Path, Path]) -> None:
    """L1-E14"""
    a, b = repos
    code, _, err = hook(bash(a, "git merge feat/a"))
    assert (code, "merge-to-main.sh" in err) == (2, True)
    assert hook(bash(b, "git merge main")) == (0, "", "")
