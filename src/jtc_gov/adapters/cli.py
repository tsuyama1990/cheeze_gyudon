import difflib
import json
import os
import re
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import click

from jtc_gov.adapters import claude_hook
from jtc_gov.adapters.repo_git import DEFAULT_BASE, WORKTREE, GitRepo, find_root
from jtc_gov.adapters.report import findings_json, format_findings, format_status
from jtc_gov.checks import run_all
from jtc_gov.domain.errors import RepoError
from jtc_gov.domain.models import CheckResult, Finding
from jtc_gov.domain.repo import Repo

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_UNEVALUATED = 2


def run_check(
    open_repo: Callable[[], Repo], *, as_json: bool, debug: bool = False
) -> tuple[int, str]:
    try:
        result = run_all(open_repo())
    except RepoError as e:
        result = CheckResult((Finding("E.repo", None, str(e)),), ())
        return EXIT_UNEVALUATED, _render(result, as_json=as_json)
    except Exception as e:  # noqa: BLE001
        message = traceback.format_exc() if debug else f"{type(e).__name__}: {e}"
        result = CheckResult((Finding("E.internal", None, message),), ())
        return EXIT_UNEVALUATED, _render(result, as_json=as_json)
    return (EXIT_OK if result.ok else EXIT_VIOLATION), _render(result, as_json=as_json)


def _render(result: CheckResult, *, as_json: bool) -> str:
    return findings_json(result) if as_json else format_findings(result)


def _opener(base: str, head: str) -> Callable[[], Repo]:
    def open_repo() -> Repo:
        return GitRepo(find_root(Path.cwd()), base, head)

    return open_repo


@click.group()
def main() -> None:
    """jtc-gov: 承認された設計だけが main に入る。"""


_base_option = click.option("--base", default=DEFAULT_BASE, show_default=True)
_head_option = click.option("--head", default=WORKTREE, show_default=True)


@main.command()
@_base_option
@_head_option
@click.option("--json", "as_json", is_flag=True)
@click.option("--debug", is_flag=True)
def check(base: str, head: str, *, as_json: bool, debug: bool) -> None:
    """K・D・T と Q.pragma を実行する。"""
    code, output = run_check(_opener(base, head), as_json=as_json, debug=debug)
    if output:
        click.echo(output)
    raise SystemExit(code)


@main.command()
@_base_option
@_head_option
def status(base: str, head: str) -> None:
    """要件ごとの状態を表示する。"""
    try:
        repo = _opener(base, head)()
        click.echo(format_status(repo, head))
    except RepoError as e:
        click.echo(f"E.repo: {e}", err=True)
        raise SystemExit(EXIT_UNEVALUATED) from e
    except Exception as e:
        click.echo(f"E.internal: {type(e).__name__}: {e}", err=True)
        raise SystemExit(EXIT_UNEVALUATED) from e


SETTINGS_PATH = Path(".claude/settings.json")
GITATTRIBUTES_PATH = Path(".gitattributes")
GITATTRIBUTES = ".specs/** text eol=lf\n"
HOOK_COMMAND = '"$CLAUDE_PROJECT_DIR"/.venv/bin/gov hook'
WRITE_MATCHER = "|".join(sorted(claude_hook.WRITE_TOOLS))


def _hook_entry(event: str, matcher: str | None = None) -> dict[str, object]:
    entry: dict[str, object] = {
        "hooks": [{"type": "command", "command": f"{HOOK_COMMAND} {event}"}]
    }
    return {"matcher": matcher, **entry} if matcher else entry


def render_settings() -> str:
    hooks = {
        "PreToolUse": [
            _hook_entry("pre-tool-use", WRITE_MATCHER),
            _hook_entry("pre-tool-use", "Bash"),
        ],
        "SessionStart": [_hook_entry("session-start")],
        "UserPromptSubmit": [_hook_entry("user-prompt-submit")],
    }
    return json.dumps({"hooks": hooks}, indent=2) + "\n"


def render_gitattributes() -> str:
    return GITATTRIBUTES


@main.command(name="hook")
@click.argument("event", type=click.Choice(claude_hook.EVENTS))
def hook_command(event: str) -> None:
    """Claude Code のフックの入口(標準入力の JSON)。"""
    claude_hook.main(event)


@main.command()
def init() -> None:
    """フック設定と .gitattributes を作る。既存と違えば差分を出して終了コード 1。"""
    try:
        root = find_root(Path.cwd())
    except RepoError as e:
        click.echo(f"E.repo: {e}", err=True)
        raise SystemExit(EXIT_VIOLATION) from e
    conflict = False
    for rel, content in (
        (SETTINGS_PATH, render_settings()),
        (GITATTRIBUTES_PATH, render_gitattributes()),
    ):
        target = root / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            click.echo(f"作成: {rel}")
            continue
        current = target.read_text(encoding="utf-8")
        if current != content:
            conflict = True
            diff = difflib.unified_diff(
                current.splitlines(),
                content.splitlines(),
                f"{rel} (現在)",
                f"{rel} (gov init)",
                lineterm="",
            )
            click.echo("\n".join(diff))
    raise SystemExit(EXIT_VIOLATION if conflict else EXIT_OK)


@dataclass(frozen=True)
class DoctorItem:
    name: str
    ok: bool
    detail: str = ""


GATE_SCRIPT = Path("scripts/gate.sh")
PRE_COMMIT_CONFIG = Path(".pre-commit-config.yaml")
WORKFLOWS_DIR = Path(".github/workflows")
YAML_COMMENT = re.compile(r"(?:^|\s)#.*$")
DUPLICATED_TOOLS = ("ruff", "mypy", "vulture", "pytest", "gate.sh", "gov check")


def _gate_script(root: Path) -> DoctorItem:
    path = root / GATE_SCRIPT
    return DoctorItem(
        f"{GATE_SCRIPT} が実行可能",
        path.is_file() and os.access(path, os.X_OK),
        "ない、または実行権限がない",
    )


def _pre_commit(root: Path) -> DoctorItem:
    path = root / PRE_COMMIT_CONFIG
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    text = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
    found = [t for t in DUPLICATED_TOOLS if t in text]
    ok = path.is_file() and not found
    return DoctorItem(f"{PRE_COMMIT_CONFIG} が衛生フックだけ", ok, ", ".join(found) or "ない")


def _settings(root: Path) -> DoctorItem:
    path = root / SETTINGS_PATH
    try:
        hooks = json.loads(path.read_text(encoding="utf-8"))["hooks"]
        ok = isinstance(hooks, dict) and "gov hook" in json.dumps(hooks)
    except (OSError, ValueError, KeyError, TypeError):
        ok = False
    return DoctorItem(f"{SETTINGS_PATH} が gov hook を呼ぶ", ok, "ない、または形式が違う")


def _calls_gate(workflow: Path) -> bool:
    try:
        lines = workflow.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    return any(GATE_SCRIPT.as_posix() in YAML_COMMENT.sub("", line) for line in lines)


def _ci_calls_gate(root: Path) -> DoctorItem:
    workflows = [*(root / WORKFLOWS_DIR).glob("*.yml"), *(root / WORKFLOWS_DIR).glob("*.yaml")]
    ok = any(_calls_gate(w) for w in workflows)
    return DoctorItem(f"CI のワークフローが {GATE_SCRIPT} を呼ぶ", ok, "呼んでいない")


def _origin_main(root: Path) -> DoctorItem:
    try:
        GitRepo(root, DEFAULT_BASE, "HEAD")
    except RepoError as e:
        return DoctorItem(f"{DEFAULT_BASE} が解決できる", ok=False, detail=str(e))
    return DoctorItem(f"{DEFAULT_BASE} が解決できる", ok=True)


CHECKS: tuple[Callable[[Path], DoctorItem], ...] = (
    _gate_script,
    _pre_commit,
    _settings,
    _ci_calls_gate,
    _origin_main,
)


@main.command()
def doctor() -> None:
    """前提を検査する。"""
    try:
        root = find_root(Path.cwd())
    except RepoError as e:
        click.echo(f"E.repo: {e}", err=True)
        raise SystemExit(EXIT_VIOLATION) from e
    items = [check(root) for check in CHECKS]
    for item in items:
        click.echo(
            f"{'OK' if item.ok else 'NG'} {item.name}" + ("" if item.ok else f": {item.detail}")
        )
    raise SystemExit(EXIT_OK if all(i.ok for i in items) else EXIT_VIOLATION)
