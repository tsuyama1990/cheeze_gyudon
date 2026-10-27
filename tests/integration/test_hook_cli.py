import json
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.adapters.cli import main
from tests.integration.test_repo_git import commit, git
from tests.support.fake_repo import with_approval

REQ = "REQ-2026-010"
TEST_FILE = (
    b'import pytest\n\n\n@pytest.mark.requirement("REQ-2026-010-F01")\n'
    b"def test_a() -> None:\n    pass\n"
)
README = {"README.md": b"r"}
APPROVED = {**README, **with_approval(REQ)}
CHANGED = {"src/a.py": b"x = 1\n", "tests/test_a.py": TEST_FILE}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A work repo whose origin/main exists (a bare remote holding main)."""
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    work.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)  # noqa: S603, S607
    git(work, "init", "-q", "-b", "main")
    git(work, "remote", "add", "origin", str(remote))
    return work


def publish(repo: Path, files: dict[str, bytes]) -> None:
    commit(repo, files)
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")


def hook(repo: Path, event: str, payload: dict[str, object]) -> tuple[int, str, str]:
    result = CliRunner().invoke(
        main, ["hook", event], input=json.dumps({**payload, "cwd": str(repo)})
    )
    return result.exit_code, result.stdout, result.stderr


def bash(command: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


@pytest.mark.requirement("REQ-2026-010-F05")
def test_commit_is_judged_on_the_worktree_push_on_head(repo: Path) -> None:
    """L1-E38, L1-E39, L1-E40"""
    publish(repo, README)
    for path, data in CHANGED.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_bytes(data)
    code, _, err = hook(repo, "pre-tool-use", bash("git add src tests && git commit -m x"))
    assert code == 2
    assert "K.a" in err
    assert hook(repo, "pre-tool-use", bash("git push"))[0] == 0  # HEAD has no such change
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "x")
    assert hook(repo, "pre-tool-use", bash("git push"))[0] == 2


@pytest.mark.requirement("REQ-2026-010-F05")
def test_valid_approval_lets_the_commit_through(repo: Path) -> None:
    publish(repo, APPROVED)
    for path, data in CHANGED.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_bytes(data)
    assert hook(repo, "pre-tool-use", bash("git commit -m x")) == (0, "", "")


@pytest.mark.requirement("REQ-2026-010-F05")
def test_write_notice_and_status_in_a_real_repo(repo: Path) -> None:
    """L1-E37, L1-E42"""
    publish(repo, README | {".specs/placeholder": b"x"})
    code, out, _ = hook(
        repo, "pre-tool-use", {"tool_name": "Write", "tool_input": {"file_path": "src/a.py"}}
    )
    assert code == 0
    assert "先に承認が必要" in out
    for event in ("session-start", "user-prompt-submit"):
        code, out, _ = hook(repo, event, {})
        assert code == 0
        assert "有効な open" in out


@pytest.mark.requirement("REQ-2026-010-F05")
def test_missing_origin_main_is_fetched_once(repo: Path) -> None:
    publish(repo, README)
    git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    for path, data in {"doc/x.md": b"d"}.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_bytes(data)
    assert hook(repo, "pre-tool-use", bash("git commit -m x")) == (0, "", "")
    assert git(repo, "rev-parse", "--verify", "origin/main")


@pytest.mark.requirement("REQ-2026-010-F05")
def test_unreachable_base_fails_open_with_a_warning(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    commit(tmp_path, README)
    code, _, err = hook(tmp_path, "pre-tool-use", bash("git commit -m x"))
    assert code == 0
    assert "検査を実行できませんでした" in err


@pytest.mark.requirement("REQ-2026-010-F05")
def test_bad_input_is_ignored(tmp_path: Path) -> None:
    """L2-I37"""
    runner = CliRunner()
    assert runner.invoke(main, ["hook", "pre-tool-use"], input="not json").exit_code == 0
    assert runner.invoke(main, ["hook", "pre-tool-use"], input="[]").exit_code == 0
    outside = json.dumps({"cwd": str(tmp_path)})
    result = runner.invoke(main, ["hook", "session-start"], input=outside)
    assert (result.exit_code, result.output) == (0, "")


@pytest.mark.requirement("REQ-2026-010-F05")
def test_installed_entry_point_rejects_with_exit_2(repo: Path) -> None:
    publish(repo, README)
    for path, data in CHANGED.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_bytes(data)
    payload = json.dumps({**bash("git commit -m x"), "cwd": str(repo)})
    gov = Path(sys.executable).parent / "gov"
    done = subprocess.run(  # noqa: S603
        [str(gov), "hook", "pre-tool-use"],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 2
    assert "K.a" in done.stderr
