import os
import subprocess
from pathlib import Path

import pytest

from tests.integration.test_repo_git import git

MERGE_SCRIPT = Path.home() / ".claude" / "bin" / "merge-to-main.sh"
GLOBAL_CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
GOOD_MESSAGE = "REQ-2026-011 F07\n\n## 証拠\nok\n\n## bonsai\n純増減 +1、削除したもの: なし\n"
BAD_MESSAGE = "merge feat/a\n"
IDENTITY = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}
OLD_WORKFLOW_DETAIL = "main上の編集・コミット禁止"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "commit", "-q", "--allow-empty", "-m", "i")
    git(tmp_path, "checkout", "-q", "-b", "feat/a")
    git(tmp_path, "commit", "-q", "--allow-empty", "-m", "a")
    git(tmp_path, "checkout", "-q", "main")
    return tmp_path


def run_script(repo: Path, message: str) -> subprocess.CompletedProcess[str]:
    msg = repo.parent / "msg.md"
    msg.write_text(message, encoding="utf-8")
    return subprocess.run(  # noqa: S603
        [str(MERGE_SCRIPT), "feat/a", str(msg)],
        cwd=repo,
        env={**os.environ, **IDENTITY},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(not MERGE_SCRIPT.is_file(), reason="merge-to-main.sh is not installed")
@pytest.mark.requirement("REQ-2026-011-F07")
def test_merge_script_checks_the_message_before_touching_main(repo: Path) -> None:
    """L1-M02"""
    before = git(repo, "rev-parse", "main")
    bad = run_script(repo, BAD_MESSAGE)
    assert bad.returncode == 1
    assert "merge message is missing" in bad.stderr
    assert git(repo, "rev-parse", "main") == before
    good = run_script(repo, GOOD_MESSAGE)
    assert good.returncode == 0
    assert git(repo, "rev-parse", "main") != before


@pytest.mark.skipif(not GLOBAL_CLAUDE_MD.is_file(), reason="no global CLAUDE.md on this machine")
@pytest.mark.requirement("REQ-2026-011-F08")
def test_global_claude_md_points_to_the_rules_table() -> None:
    """L1-M03: only the Workflow section was moved; the other sections stay (see decisions.md)."""
    text = GLOBAL_CLAUDE_MD.read_text(encoding="utf-8")
    assert "AGENT.md" in text
    assert OLD_WORKFLOW_DETAIL not in text
