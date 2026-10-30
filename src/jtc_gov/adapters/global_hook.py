import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, NoReturn

from jtc_gov.adapters.claude_hook import EXIT_REJECT, WRITE_TOOLS, HookOutcome
from jtc_gov.derive.git_commands import GitInvocation, parse_git_invocations

EVENTS: Final = ("global-guard",)
PROTECTED_BRANCHES: Final = ("main", "master")
GIT_TIMEOUT_SECONDS: Final = 5
APPROVAL_PATH: Final = re.compile(r"(?:^|/)\.specs/[^/]+/approval\.json$")
APPROVAL_NAME: Final = "approval.json"
WRITE_TOKENS: Final = re.compile(
    r"(?:>|\btee\b|\bsed\s+-i\b|\bcp\b|\bmv\b|\bpython3?\b|\bdd\b|\binstall\b)"
)
REDIRECT_TO_STREAM: Final = re.compile(r"\d*>&\d+|\d*>\s*/dev/null")
MERGE_SCRIPT: Final = "merge-to-main.sh"
ADD_ALL_ARGS: Final = frozenset({"-A", "--all", "."})
MERGE_CONTINUATIONS: Final = frozenset({"--abort", "--continue", "--quit"})
COMMIT_DENIED: Final = "{branch} への直接のコミットは禁止です。作業ブランチを切ってください"
EDIT_DENIED: Final = "{branch} 上の直接の編集は禁止です。作業ブランチを切ってください"
ADD_ALL_DENIED: Final = "git add -A / --all / . は禁止です。パスを指定してください"
MERGE_DENIED: Final = "{branch} 上の git merge は禁止です。merge-to-main.sh を使ってください"
PUSH_ASK: Final = "git push は利用者の指示があるときだけ行います"
MERGE_SCRIPT_ASK: Final = "merge-to-main.sh は結果が変わるマージです。承認してください"
APPROVAL_ASK: Final = "approval.json は人間が作ります。承認してください"
RANK: Final = {"allow": 0, "ask": 1, "deny": 2}

Kind = Literal["allow", "ask", "deny"]


@dataclass(frozen=True)
class Decision:
    kind: Kind
    reason: str = ""


ALLOW: Final = Decision("allow")


def strongest(decisions: Iterable[Decision]) -> Decision:
    return max(decisions, key=lambda d: RANK[d.kind], default=ALLOW)


def decide_invocation(inv: GitInvocation, branch: str | None) -> Decision:
    protected = branch in PROTECTED_BRANCHES
    if inv.subcommand == "commit" and protected:
        return Decision("deny", COMMIT_DENIED.format(branch=branch))
    if inv.subcommand == "add" and ADD_ALL_ARGS & set(inv.args):
        return Decision("deny", ADD_ALL_DENIED)
    if inv.subcommand == "merge" and protected and not MERGE_CONTINUATIONS & set(inv.args):
        return Decision("deny", MERGE_DENIED.format(branch=branch))
    if inv.subcommand == "push":
        return Decision("ask", PUSH_ASK)
    return ALLOW


def decide_command_text(command: str) -> Decision:
    decisions = []
    if MERGE_SCRIPT in command:
        decisions.append(Decision("ask", MERGE_SCRIPT_ASK))
    if APPROVAL_NAME in command and WRITE_TOKENS.search(REDIRECT_TO_STREAM.sub("", command)):
        decisions.append(Decision("ask", APPROVAL_ASK))
    return strongest(decisions)


def decide_write_path(relative_path: str, branch: str | None, *, ignored: bool) -> Decision:
    decisions = []
    if APPROVAL_PATH.search(relative_path):
        decisions.append(Decision("ask", APPROVAL_ASK))
    if not ignored and branch in PROTECTED_BRANCHES:
        decisions.append(Decision("deny", EDIT_DENIED.format(branch=branch)))
    return strongest(decisions)


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(directory), *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _toplevel(directory: Path) -> Path | None:
    while not directory.is_dir() and directory != directory.parent:
        directory = directory.parent
    done = _git(directory, "rev-parse", "--show-toplevel")
    return Path(done.stdout.strip()) if done and done.returncode == 0 else None


def _branch(repo: Path) -> str | None:
    done = _git(repo, "branch", "--show-current")
    return (done.stdout.strip() or None) if done and done.returncode == 0 else None


def _guard_write(cwd: Path, raw: str) -> Decision:
    path = Path(os.path.normpath(cwd / raw))
    repo = _toplevel(path.parent)
    if repo is None:
        return ALLOW
    relative = path.relative_to(repo).as_posix() if path.is_relative_to(repo) else raw
    done = _git(repo, "check-ignore", "-q", relative)
    return decide_write_path(
        relative, _branch(repo), ignored=done is not None and done.returncode == 0
    )


def _guard_invocation(cwd: Path, inv: GitInvocation) -> Decision:
    repo = _toplevel(Path(os.path.normpath(cwd / (inv.directory or "."))))
    decision = decide_invocation(inv, _branch(repo) if repo else None)
    return (
        Decision(decision.kind, f"{decision.reason} [{repo}]")
        if repo and decision.reason
        else decision
    )


def _guard_bash(cwd: Path, command: str) -> Decision:
    return strongest(
        [decide_command_text(command)]
        + [_guard_invocation(cwd, inv) for inv in parse_git_invocations(command)]
    )


@dataclass(frozen=True)
class ToolCall:
    cwd: str
    command: str | None = None
    path: str | None = None


def decide_call(call: ToolCall) -> Decision:
    if call.path is not None:
        return _guard_write(Path(call.cwd), call.path)
    if call.command is not None:
        return _guard_bash(Path(call.cwd), call.command)
    return ALLOW


def claude_call(payload: dict[str, object]) -> ToolCall | None:
    cwd, tool_input = payload.get("cwd"), payload.get("tool_input")
    if not isinstance(cwd, str) or not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    command = tool_input.get("command")
    if payload.get("tool_name") in WRITE_TOOLS and isinstance(raw, str):
        return ToolCall(cwd, path=raw)
    if payload.get("tool_name") == "Bash" and isinstance(command, str):
        return ToolCall(cwd, command=command)
    return None


def _claude_outcome(decision: Decision) -> HookOutcome:
    if decision.kind == "deny":
        return HookOutcome(EXIT_REJECT, stderr=f"Blocked: {decision.reason}")
    if decision.kind == "ask":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": decision.reason,
            }
        }
        return HookOutcome(0, stdout=json.dumps(output, ensure_ascii=False))
    return HookOutcome(0)


def guard(payload: dict[str, object]) -> HookOutcome:
    call = claude_call(payload)
    return HookOutcome(0) if call is None else _claude_outcome(decide_call(call))


def emit(outcome: HookOutcome) -> NoReturn:
    if outcome.stdout:
        sys.stdout.write(outcome.stdout + "\n")
    if outcome.stderr:
        sys.stderr.write(outcome.stderr + "\n")
    raise SystemExit(outcome.exit_code)


def main(event: str) -> NoReturn:
    outcome = HookOutcome(0)
    try:
        payload = json.loads(sys.stdin.read())
        if event in EVENTS and isinstance(payload, dict):
            outcome = guard(payload)
    except Exception:  # noqa: BLE001 - the hook is advisory (DEC-002)
        outcome = HookOutcome(0)
    emit(outcome)
