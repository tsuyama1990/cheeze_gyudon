import traceback
from collections.abc import Callable
from pathlib import Path

import click

from jtc_gov.adapters.repo_git import WORKTREE, GitRepo, find_root
from jtc_gov.adapters.report import findings_json, format_findings, format_status
from jtc_gov.checks import run_all
from jtc_gov.domain.errors import RepoError
from jtc_gov.domain.models import CheckResult, Finding
from jtc_gov.domain.repo import Repo

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_UNEVALUATED = 2
DEFAULT_BASE = "origin/main"


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
