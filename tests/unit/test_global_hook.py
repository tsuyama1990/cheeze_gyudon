import pytest

from jtc_gov.adapters.global_hook import (
    APPROVAL_PATH,
    Decision,
    decide_command_text,
    decide_invocation,
    decide_write_path,
    strongest,
)
from jtc_gov.derive.git_commands import GitInvocation

ALLOW, ASK, DENY = Decision("allow"), Decision("ask", "r"), Decision("deny", "r")
APPROVAL = ".specs/R/approval.json"


def inv(subcommand: str, *args: str) -> GitInvocation:
    return GitInvocation(subcommand, args, None)


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    ("invocation", "branch", "kind"),
    [
        (inv("commit"), "main", "deny"),
        (inv("commit"), "master", "deny"),
        (inv("commit"), "feat/x", "allow"),
        (inv("commit"), None, "allow"),
        (inv("add", "-A"), "feat/x", "deny"),
        (inv("add", "--all"), "feat/x", "deny"),
        (inv("add", "."), "feat/x", "deny"),
        (inv("add", "a.py"), "feat/x", "allow"),
        (inv("merge", "feat"), "main", "deny"),
        (inv("merge", "--abort"), "main", "allow"),
        (inv("merge", "main"), "feat/x", "allow"),
        (inv("push"), "feat/x", "ask"),
    ],
)
def test_invocation_table(invocation: GitInvocation, branch: str | None, kind: str) -> None:
    """L3-U10"""
    assert decide_invocation(invocation, branch).kind == kind


@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    ("decisions", "expected"),
    [([], ALLOW), ([ALLOW, ASK], ASK), ([ASK, DENY, ALLOW], DENY), ([ALLOW, ALLOW], ALLOW)],
)
def test_strongest_wins(decisions: list[Decision], expected: Decision) -> None:
    """L3-U11"""
    assert strongest(decisions) == expected


@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    ("path", "matches"),
    [
        (".specs/REQ-1/approval.json", True),
        ("a/b/.specs/R/approval.json", True),
        ("approval.json", False),
        (".specs/R/approval.json.bak", False),
        (".specs/R/x/approval.json", False),
    ],
)
def test_approval_path_pattern(path: str, *, matches: bool) -> None:
    """L3-U12"""
    assert bool(APPROVAL_PATH.search(path)) is matches


@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    "command",
    [
        f"echo {{}} > {APPROVAL}",
        f"echo {{}} >> {APPROVAL}",
        f"echo x | tee {APPROVAL}",
        f"sed -i s/a/b/ {APPROVAL}",
        f"cp x {APPROVAL}",
        f"mv x {APPROVAL}",
        f"python3 -c \"open('{APPROVAL}', 'w')\"",
    ],
)
def test_writing_approval_asks(command: str) -> None:
    """L3-U13"""
    assert decide_command_text(command).kind == "ask"


@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    "command",
    [
        f"cat {APPROVAL}",
        f"grep state {APPROVAL}",
        f"jq . {APPROVAL}",
        f"sha256sum {APPROVAL}",
        f"git diff -- {APPROVAL}",
        f"cat {APPROVAL} 2>&1",
        f"cat {APPROVAL} 2>/dev/null",
    ],
)
def test_reading_approval_is_allowed(command: str) -> None:
    """L3-U14"""
    assert decide_command_text(command).kind == "allow"


@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    "command",
    [
        "~/.claude/bin/merge-to-main.sh feat/a m.md",
        "bash merge-to-main.sh x",
        "echo merge-to-main.sh",
    ],
)
def test_merge_script_asks(command: str) -> None:
    """L3-U15: the word alone triggers it (a known false positive, fixed here)."""
    assert decide_command_text(command).kind == "ask"


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    ("path", "branch", "ignored", "kind"),
    [
        (APPROVAL, "main", False, "deny"),
        (APPROVAL, "feat/x", False, "ask"),
        ("src/a.py", "main", False, "deny"),
        ("src/a.py", "feat/x", False, "allow"),
        ("build/x", "main", True, "allow"),
        ("src/a.py", None, False, "allow"),
    ],
)
def test_write_path_table(path: str, branch: str | None, kind: str, *, ignored: bool) -> None:
    """L3-U16"""
    assert decide_write_path(path, branch, ignored=ignored).kind == kind
