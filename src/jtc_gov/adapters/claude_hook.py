import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, NoReturn

from jtc_gov.adapters.repo_git import WORKTREE, GitRepo
from jtc_gov.adapters.report import format_findings, short_status
from jtc_gov.checks import run_all
from jtc_gov.derive.approvals import valid_open
from jtc_gov.domain.errors import RepoError
from jtc_gov.domain.gates import SRC_PREFIX
from jtc_gov.domain.repo import Repo

GIT_COMMAND: Final = re.compile(
    r"(?:^|[\s;&|(`{\"'])git(?:\s+-\S+(?:\s+[^\s-]\S*)?)*\s+(commit|push)\b"
)
EVENTS: Final = ("pre-tool-use", "session-start", "user-prompt-submit")
WRITE_TOOLS: Final = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
REJECTING_RULES: Final = ("K.", "D.")
BASE: Final = "origin/main"
HEAD_COMMIT: Final = "HEAD"
FETCH_TIMEOUT_SECONDS: Final = 60
EXIT_REJECT: Final = 2
SPECS_DIR: Final = ".specs"
APPROVAL_NOTICE: Final = "src/ を変更し、テストまたは仕様も変える場合は、先に承認が必要です"

RepoFactory = Callable[[Path, str], Repo]


@dataclass(frozen=True)
class HookOutcome:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


def classify_git(command: str) -> Literal["commit", "push"] | None:
    found = {m.group(1) for m in GIT_COMMAND.finditer(command)}
    if "commit" in found:
        return "commit"
    return "push" if "push" in found else None


def _written_path(root: Path, tool_input: object) -> str | None:
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str):
        return None
    try:
        return (root / raw).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _notice(repo: Repo, root: Path, payload: dict[str, object]) -> HookOutcome:
    path = _written_path(root, payload.get("tool_input"))
    if path is None or not path.startswith(SRC_PREFIX) or len(valid_open(repo, "base")) == 1:
        return HookOutcome(0)
    return HookOutcome(0, stdout=f"{short_status(repo)}\n{APPROVAL_NOTICE}")


def _gate(repo_factory: RepoFactory, root: Path, kind: str) -> HookOutcome:
    result = run_all(repo_factory(root, WORKTREE if kind == "commit" else HEAD_COMMIT))
    rejecting = tuple(f for f in result.findings if f.rule.startswith(REJECTING_RULES))
    if rejecting:
        return HookOutcome(EXIT_REJECT, stderr=format_findings(result))
    if result.findings:
        return HookOutcome(0, stderr=f"gov hook: 警告(CI で失敗します)\n{format_findings(result)}")
    return HookOutcome(0)


def _command(payload: dict[str, object]) -> str | None:
    tool_input = payload.get("tool_input")
    if payload.get("tool_name") != "Bash" or not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    return command if isinstance(command, str) else None


def _run(
    kind: str | None,
    event: str,
    payload: dict[str, object],
    root: Path,
    repo_factory: RepoFactory,
) -> HookOutcome:
    if kind is not None:
        return _gate(repo_factory, root, kind)
    if event != "pre-tool-use":
        return HookOutcome(0, stdout=short_status(repo_factory(root, WORKTREE)))
    if payload.get("tool_name") in WRITE_TOOLS:
        return _notice(repo_factory(root, WORKTREE), root, payload)
    return HookOutcome(0)


def handle(
    event: str, payload: dict[str, object], root: Path, repo_factory: RepoFactory
) -> HookOutcome:
    command = _command(payload)
    kind = classify_git(command) if event == "pre-tool-use" and command is not None else None
    if event not in EVENTS or (kind is None and not (root / SPECS_DIR).is_dir()):
        return HookOutcome(0)
    try:
        return _run(kind, event, payload, root, repo_factory)
    except Exception as e:  # noqa: BLE001 - the hook is advisory; the authority is CI
        warning = f"gov hook: 検査を実行できませんでした: {e}(権威は CI)"
        return HookOutcome(0, stderr=warning if kind is not None else "")


def open_repo(root: Path, head: str) -> Repo:
    try:
        return GitRepo(root, BASE, head)
    except RepoError:
        done = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "fetch", "origin", "main"],  # noqa: S607
            capture_output=True,
            check=False,
            timeout=FETCH_TIMEOUT_SECONDS,
        )
        if done.returncode != 0:
            raise
        return GitRepo(root, BASE, head)


def main(event: str) -> NoReturn:
    try:
        payload = json.loads(sys.stdin.read())
        cwd = Path(payload["cwd"])
        top = subprocess.run(  # noqa: S603
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],  # noqa: S607
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError):
        raise SystemExit(0) from None
    outcome = handle(event, payload, Path(top), open_repo)
    if outcome.stdout:
        sys.stdout.write(outcome.stdout + "\n")
    if outcome.stderr:
        sys.stderr.write(outcome.stderr + "\n")
    raise SystemExit(outcome.exit_code)
