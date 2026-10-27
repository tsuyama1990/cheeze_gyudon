from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.adapters.cli import main
from tests.integration.test_repo_git import commit, git, root  # noqa: F401
from tests.support.fake_repo import with_approval

REQ = "REQ-2026-010"
README = {"README.md": b"r\n"}
TEST = (
    b"import pytest\n\n\n"
    b'@pytest.mark.requirement("REQ-2026-010-F01")\n'
    b"def test_a() -> None:\n    pass\n"
)
PRAGMA = b"x = 1  # pragma: no cover\n"


def verdict(*args: str) -> tuple[int, str]:
    result = CliRunner().invoke(main, ["check", *args])
    return result.exit_code, result.output


def merge_result(repo: Path, branch: str) -> str:
    """What CI checks out for a pull request: main merged with the topic (a merge commit)."""
    git(repo, "checkout", "-q", "-b", "pr-merge", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge", branch)
    return git(repo, "rev-parse", "HEAD")


@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.spec("L2-I08", "L2-I48", "L2-I53")
@pytest.mark.parametrize(
    ("files", "expected_rule"),
    [
        ({"src/a.py": b"x = 1\n", "tests/test_a.py": TEST}, "K.a"),
        ({"src/a.py": PRAGMA}, "Q.pragma"),
        ({"doc/x.md": b"d\n"}, ""),
    ],
    ids=["unapproved-behavior", "new-pragma", "docs-only"],
)
def test_worktree_and_ci_merge_result_agree(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, bytes],
    expected_rule: str,
) -> None:
    monkeypatch.chdir(root)
    commit(root, {**README, **with_approval(REQ, "closed")}, "base")
    git(root, "checkout", "-q", "-b", "topic")
    commit(root, {**README, **with_approval(REQ, "closed"), **files}, "topic")
    git(root, "checkout", "-q", "main")
    commit(root, {**README, **with_approval(REQ, "closed"), "other.txt": b"o\n"}, "main moved")
    git(root, "checkout", "-q", "topic")
    stale = verdict("--base", "main", "--head", "HEAD")
    git(root, "checkout", "-q", "main")
    merged = merge_result(root, "topic")
    ci = verdict("--base", "main", "--head", merged)
    for code, output in (stale, ci):
        assert (code == 0) is (expected_rule == "")
        assert expected_rule in output
