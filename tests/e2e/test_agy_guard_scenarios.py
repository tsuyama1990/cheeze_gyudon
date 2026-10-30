import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.adapters.cli import main
from tests.support.guard_repos import agy_run, agy_write, bash, make_repos

APPROVAL = ".specs/REQ-X/approval.json"


def hook(event: str, stdin: str) -> tuple[int, str]:
    result = CliRunner().invoke(main, ["hook", event], input=stdin)
    return result.exit_code, result.stdout


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    return make_repos(tmp_path)


@pytest.mark.requirement("REQ-2026-012-F01")
def test_commit_on_main_is_denied_naming_the_branch(repos: tuple[Path, Path]) -> None:
    """L1-E01"""
    a, _ = repos
    code, out = hook("agy-pre-tool-use", agy_run(a, "git commit -m x"))
    assert code == 0
    answer = json.loads(out)
    assert answer["decision"] == "deny"
    assert "main" in answer["reason"]


@pytest.mark.requirement("REQ-2026-012-F01")
def test_push_on_a_work_branch_asks(repos: tuple[Path, Path]) -> None:
    """L1-E02"""
    _, b = repos
    code, out = hook("agy-pre-tool-use", agy_run(b, "git push"))
    assert (code, json.loads(out)["decision"]) == (0, "ask")


@pytest.mark.requirement("REQ-2026-012-F01")
def test_approval_json_write_asks(repos: tuple[Path, Path]) -> None:
    """L1-E03"""
    _, b = repos
    assert json.loads(hook("agy-pre-tool-use", agy_write(b, APPROVAL))[1])["decision"] == "ask"


@pytest.mark.requirement("REQ-2026-012-F01")
def test_allowed_operations_print_nothing(repos: tuple[Path, Path]) -> None:
    """L1-E04"""
    _, b = repos
    assert hook("agy-pre-tool-use", agy_run(b, "git status")) == (0, "")
    assert hook("agy-pre-tool-use", agy_write(b, "src/a.py")) == (0, "")


@pytest.mark.requirement("REQ-2026-012-F02")
def test_add_all_on_main_is_denied_for_both_agents(repos: tuple[Path, Path]) -> None:
    """L1-E05"""
    a, _ = repos
    assert hook("global-guard", bash(a, "git add -A"))[0] == 2
    assert json.loads(hook("agy-pre-tool-use", agy_run(a, "git add -A"))[1])["decision"] == "deny"
