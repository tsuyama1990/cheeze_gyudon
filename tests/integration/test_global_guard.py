import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.adapters.cli import main
from tests.support.guard_repos import bash, make_repos, write

APPROVAL = ".specs/REQ-X/approval.json"


def run(stdin: str, event: str = "global-guard") -> tuple[int, str, str]:
    result = CliRunner().invoke(main, ["hook", event], input=stdin)
    return result.exit_code, result.stdout, result.stderr


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    return make_repos(tmp_path)


@pytest.mark.requirement("REQ-2026-011-F04")
def test_commit_on_main_names_branch_and_repo(repos: tuple[Path, Path]) -> None:
    """L2-I07"""
    a, _ = repos
    code, _, err = run(bash(a, "git commit -m x"))
    assert code == 2
    assert "main" in err
    assert str(a) in err


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.parametrize(
    ("command", "code"),
    [
        ("git -C B commit -m x", 0),
        ("git -C A commit -m x", 2),
        ("cd B && git commit -m x", 0),
        ("cd A && git commit -m x", 2),
        ("cd A; cd ../B && git commit -m x", 0),
        ("cd B; cd ../A && git commit -m x", 2),
    ],
)
def test_relative_targets_are_resolved_from_cwd(
    repos: tuple[Path, Path], command: str, code: int
) -> None:
    """L2-I08: the session cwd (the parent of both) decides nothing."""
    a, _ = repos
    assert run(bash(a.parent, command))[0] == code


@pytest.mark.requirement("REQ-2026-011-F04")
def test_write_paths_relative_missing_and_ignored(repos: tuple[Path, Path]) -> None:
    """L2-I09"""
    a, b = repos
    (a / ".gitignore").write_text("build/\n")
    assert run(write(a, "src/a.py"))[0] == 2
    assert run(write(a, "new/dir/deep/a.py"))[0] == 2
    assert run(write(a, "build/out.txt"))[0] == 0
    assert run(write(b, "src/a.py"))[0] == 0
    assert run(write(a, str(b / "src/a.py")))[0] == 0


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.parametrize(
    ("command", "code"),
    [
        ("git add -A", 2),
        ("git add --all", 2),
        ("git add .", 2),
        ("git add src/a.py", 0),
        ("git -C ../B add -A", 2),
    ],
)
def test_add_all_is_denied(repos: tuple[Path, Path], command: str, code: int) -> None:
    """L2-I10"""
    a, _ = repos
    assert run(bash(a, command))[0] == code


@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    "command", ["git push", "git -C B push", "~/.claude/bin/merge-to-main.sh feat/a m.md"]
)
def test_push_and_merge_script_ask(repos: tuple[Path, Path], command: str) -> None:
    """L2-I11"""
    a, _ = repos
    code, out, _ = run(bash(a.parent, command))
    decision = json.loads(out)["hookSpecificOutput"]
    assert code == 0
    assert decision["permissionDecision"] == "ask"
    assert decision["permissionDecisionReason"]


@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    ("command", "asks"),
    [
        (f"echo x > {APPROVAL}", True),
        (f"tee {APPROVAL}", True),
        (f"sed -i s/a/b/ {APPROVAL}", True),
        (f"cp x {APPROVAL}", True),
        (f"mv x {APPROVAL}", True),
        (f"python -c \"open('{APPROVAL}')\"", True),
        (f"cat {APPROVAL}", False),
        (f"grep state {APPROVAL}", False),
        (f"jq . {APPROVAL}", False),
        (f"sha256sum {APPROVAL}", False),
        (f"git diff -- {APPROVAL}", False),
    ],
)
def test_approval_is_asked_for_writes_only(
    repos: tuple[Path, Path], command: str, *, asks: bool
) -> None:
    """L2-I12"""
    _, b = repos
    code, out, _ = run(bash(b, command))
    assert code == 0
    assert ("ask" in out) is asks
    code, out, _ = run(write(b, APPROVAL))
    assert (code, "ask" in out) == (0, True)


@pytest.mark.requirement("REQ-2026-011-F05")
def test_merge_on_main_is_denied_and_points_to_the_script(repos: tuple[Path, Path]) -> None:
    """L2-I13"""
    a, b = repos
    code, _, err = run(bash(a, "git merge feat/a"))
    assert (code, "merge-to-main.sh" in err) == (2, True)
    assert run(bash(a, "git merge --abort"))[0] == 0
    assert run(bash(b, "git merge main"))[0] == 0


@pytest.mark.requirement("REQ-2026-011-F05")
def test_strongest_decision_wins(repos: tuple[Path, Path]) -> None:
    """L2-I14"""
    a, b = repos
    assert run(bash(a, "git push && git commit -m x"))[0] == 2
    code, out, _ = run(bash(b, "git push && git status"))
    assert (code, "ask" in out) == (0, True)


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.requirement("REQ-2026-011-F05")
def test_broken_input_and_missing_git_never_block(
    repos: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """L2-I15"""
    a, _ = repos
    assert run("not json") == (0, "", "")
    assert run("[]") == (0, "", "")
    assert run(bash(a.parent / "missing", "git commit -m x"))[0] == 0
    monkeypatch.setenv("PATH", "")
    assert run(bash(a, "git commit -m x")) == (0, "", "")


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.requirement("REQ-2026-011-F05")
def test_hook_accepts_the_new_event_and_rejects_unknown_ones() -> None:
    """L2-I16"""
    assert run("{}", "global-guard")[0] == 0
    for event in ("pre-tool-use", "session-start", "user-prompt-submit"):
        assert run("{}", event)[0] == 0
    assert run("{}", "global-stop")[0] == 2
