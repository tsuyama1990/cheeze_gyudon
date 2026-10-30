import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.adapters.cli import main
from jtc_gov.domain.machinery import machinery_reason
from tests.support.guard_repos import agy_payload, agy_run, agy_write, bash, make_repos

APPROVAL = ".specs/REQ-X/approval.json"
EVENT = "agy-pre-tool-use"


def run(stdin: str, event: str = EVENT) -> tuple[int, str, str]:
    result = CliRunner().invoke(main, ["hook", event], input=stdin)
    return result.exit_code, result.stdout, result.stderr


def decision(out: str) -> str:
    return str(json.loads(out)["decision"]) if out else ""


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    return make_repos(tmp_path)


@pytest.mark.requirement("REQ-2026-012-F01")
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git -C B commit -m x", ""),
        ("git -C A commit -m x", "deny"),
        ("cd B && git commit -m x", ""),
        ("cd A && git commit -m x", "deny"),
        ("cd A; cd ../B && git commit -m x", ""),
    ],
)
def test_relative_targets_are_resolved_from_the_workspace(
    repos: tuple[Path, Path], command: str, expected: str
) -> None:
    """L2-I01"""
    a, _ = repos
    code, out, _ = run(agy_run(a.parent, command))
    assert (code, decision(out)) == (0, expected)


@pytest.mark.requirement("REQ-2026-012-F01")
def test_cwd_argument_or_workspace_decides_the_repository(repos: tuple[Path, Path]) -> None:
    """L2-I02"""
    a, b = repos
    assert decision(run(agy_run(a, "git commit -m x", cwd=str(a)))[1]) == "deny"
    assert decision(run(agy_run(a.parent, "git commit -m x", cwd="A"))[1]) == "deny"
    assert decision(run(agy_run(a.parent, "git commit -m x", cwd="B"))[1]) == ""
    assert decision(run(agy_run(a, "git commit -m x"))[1]) == "deny"
    assert decision(run(agy_run(b, "git commit -m x"))[1]) == ""


@pytest.mark.requirement("REQ-2026-012-F01")
@pytest.mark.parametrize(
    "tool", ["write_to_file", "replace_file_content", "multi_replace_file_content"]
)
def test_target_file_tools_are_denied_on_main(repos: tuple[Path, Path], tool: str) -> None:
    """L2-I03"""
    a, b = repos
    (a / ".gitignore").write_text("build/\n")
    assert decision(run(agy_write(a, "src/a.py", tool))[1]) == "deny"
    assert decision(run(agy_write(a, "new/dir/a.py", tool))[1]) == "deny"
    assert decision(run(agy_write(a, str(a / "src/a.py"), tool))[1]) == "deny"
    assert decision(run(agy_write(a, "build/out.txt", tool))[1]) == ""
    assert decision(run(agy_write(b, "src/a.py", tool))[1]) == ""


@pytest.mark.requirement("REQ-2026-012-F01")
@pytest.mark.parametrize("tool", ["write_file", "edit_file"])
def test_path_tools_are_denied_on_main(repos: tuple[Path, Path], tool: str) -> None:
    """L2-I03"""
    a, b = repos
    assert decision(run(agy_write(a, "src/a.py", tool))[1]) == "deny"
    assert decision(run(agy_write(b, "src/a.py", tool))[1]) == ""


@pytest.mark.requirement("REQ-2026-012-F01")
@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git -C B push origin x",
        "~/.claude/bin/merge-to-main.sh feat/a m.md",
        f"echo x > {APPROVAL}",
    ],
)
def test_push_merge_script_and_approval_writes_ask(repos: tuple[Path, Path], command: str) -> None:
    """L2-I04"""
    a, _ = repos
    code, out, _ = run(agy_run(a.parent, command))
    assert (code, decision(out)) == (0, "ask")
    assert json.loads(out)["reason"]


@pytest.mark.requirement("REQ-2026-012-F01")
def test_approval_file_write_tool_asks(repos: tuple[Path, Path]) -> None:
    """L2-I04"""
    _, b = repos
    assert decision(run(agy_write(b, APPROVAL, "write_file"))[1]) == "ask"


@pytest.mark.requirement("REQ-2026-012-F01")
@pytest.mark.parametrize("tool", ["view_file", "grep_search", "list_dir"])
def test_other_tools_pass_silently(repos: tuple[Path, Path], tool: str) -> None:
    """L2-I05"""
    a, _ = repos
    assert run(agy_payload(a, tool, {"Path": "src/a.py"})) == (0, "", "")


@pytest.mark.requirement("REQ-2026-012-F01")
def test_broken_input_and_missing_git_never_block(
    repos: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """L2-I06"""
    a, _ = repos
    assert run("not json") == (0, "", "")
    assert run("[]") == (0, "", "")
    assert run(json.dumps({"toolCall": {"name": "run_command", "args": {}}})) == (0, "", "")
    assert run(json.dumps({"workspacePaths": []})) == (0, "", "")
    monkeypatch.setenv("PATH", "")
    assert run(agy_run(a, "git commit -m x")) == (0, "", "")


@pytest.mark.requirement("REQ-2026-012-F01")
def test_hook_event_choices() -> None:
    """L2-I07"""
    for event in ("pre-tool-use", "session-start", "user-prompt-submit", "global-guard", EVENT):
        assert run("{}", event)[0] == 0
    assert run("{}", "global-stop")[0] == 2


@pytest.mark.requirement("REQ-2026-012-F02")
@pytest.mark.parametrize(
    ("command", "claude_code", "agy_decision"),
    [
        ("git add -A", 2, "deny"),
        ("git merge feat", 2, "deny"),
        ("git push", 0, "ask"),
    ],
)
def test_claude_and_agy_judge_alike(
    repos: tuple[Path, Path], command: str, claude_code: int, agy_decision: str
) -> None:
    """L2-I08"""
    a, _ = repos
    code, out, _ = run(bash(a, command), "global-guard")
    assert code == claude_code
    assert (claude_code == 2 or "ask" in out) is True
    assert decision(run(agy_run(a, command))[1]) == agy_decision


@pytest.mark.requirement("REQ-2026-012-F02")
def test_claude_decisions_are_unchanged(repos: tuple[Path, Path]) -> None:
    """L2-I09"""
    a, b = repos
    assert run(bash(a, "git commit -m x"), "global-guard")[0] == 2
    assert run(bash(b, "git status"), "global-guard") == (0, "", "")


@pytest.mark.requirement("REQ-2026-012-F03")
def test_agents_md_changes_need_a_human_merge() -> None:
    """L2-I10"""
    assert machinery_reason("AGENTS.md")
