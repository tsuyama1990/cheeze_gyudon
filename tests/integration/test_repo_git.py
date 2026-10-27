import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from jtc_gov.adapters.repo_git import GitRepo
from jtc_gov.domain.errors import RepoError
from jtc_gov.domain.models import Change
from tests.support.fake_repo import FakeRepo

Files = Mapping[str, bytes]
Commit = Callable[[Files], str]


def git(root: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    cmd = ["git", "-C", str(root), *args]
    done = subprocess.run(cmd, capture_output=True, check=True, env=env, text=True)  # noqa: S603
    return done.stdout.strip()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


def commit(root: Path, files: Files, msg: str = "c") -> str:
    for path in git(root, "ls-files").splitlines():
        (root / path).unlink()
    for path, data in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_bytes(data)
    git(root, "add", "-A")
    git(root, "commit", "-q", "--allow-empty", "-m", msg)
    return git(root, "rev-parse", "HEAD")


BASE = {
    "a.txt": b"alpha\n" * 5,
    "dir/b.txt": b"bee\n" * 5,
    "gone.txt": b"x" * 40,
    "mv.txt": b"move me\n" * 6,
}
HEAD = {
    "a.txt": b"alpha\n" * 5 + b"more\n",
    "dir/b.txt": b"bee\n" * 5,
    "new.txt": b"n",
    "moved.txt": b"move me\n" * 6,
}
RENAMES = {"mv.txt": "moved.txt"}


def _pair(root: Path) -> tuple[GitRepo, FakeRepo]:
    base = commit(root, BASE, "base")
    head = commit(root, HEAD, "head")
    return GitRepo(root, base, head), FakeRepo(BASE, HEAD, RENAMES)


@pytest.mark.requirement("REQ-2026-010-F01")
def test_conformance_with_fake_repo(root: Path) -> None:
    real, fake = _pair(root)
    for ref in ("base", "head"):
        assert real.list(ref) == fake.list(ref)
        for path in [*BASE, *HEAD, "missing.txt"]:
            assert real.read(path, ref) == fake.read(path, ref)
    assert sorted(map(str, real.changes()), key=str) == sorted(map(str, fake.changes()), key=str)


@pytest.mark.requirement("REQ-2026-010-F06")
def test_list_is_full_path_ascending(root: Path) -> None:
    files = {"a/x": b"1", "a-b": b"2", "a.c": b"3", "日本語 名.txt": b"4"}
    head = commit(root, files)
    repo = GitRepo(root, head, head)
    assert list(repo.list("head")) == sorted(files)
    assert repo.read("日本語 名.txt", "head") == b"4"


@pytest.mark.requirement("REQ-2026-010-F05")
def test_worktree_list_and_changes(root: Path) -> None:
    base = commit(
        root, {"keep.txt": b"k", "del.txt": b"d", "mod.txt": b"m", ".gitignore": b"ign.txt\n"}
    )
    (root / "del.txt").unlink()
    (root / "mod.txt").write_bytes(b"m2")
    (root / "new.txt").write_bytes(b"n")
    (root / "ign.txt").write_bytes(b"i")
    repo = GitRepo(root, base, "worktree")
    assert list(repo.list("head")) == [".gitignore", "keep.txt", "mod.txt", "new.txt"]
    assert repo.read("del.txt", "head") is None
    assert repo.read("ign.txt", "head") is None
    assert repo.read("new.txt", "head") == b"n"
    assert repo.read("del.txt", "base") == b"d"
    got = {(c.old_path, c.new_path, c.status) for c in repo.changes()}
    assert got == {
        ("del.txt", None, "deleted"),
        ("mod.txt", "mod.txt", "modified"),
        (None, "new.txt", "added"),
    }


@pytest.mark.requirement("REQ-2026-010-F05")
def test_worktree_rename_before_add_is_delete_plus_add(root: Path) -> None:
    base = commit(root, {"src.txt": b"content\n" * 10})
    (root / "src.txt").rename(root / "dst.txt")
    got = {(c.old_path, c.new_path, c.status) for c in GitRepo(root, base, "worktree").changes()}
    assert got == {("src.txt", None, "deleted"), (None, "dst.txt", "added")}
    git(root, "add", "-A")
    staged = GitRepo(root, base, "worktree").changes()
    assert staged == [Change("src.txt", "dst.txt", "renamed")]


@pytest.mark.requirement("REQ-2026-010-F01")
def test_rename_with_edit_and_mode_only_change(root: Path) -> None:
    base = commit(root, {"r.txt": b"line\n" * 20, "x.sh": b"echo\n"})
    (root / "r.txt").rename(root / "r2.txt")
    (root / "r2.txt").write_bytes(b"line\n" * 20 + b"extra\n")
    (root / "x.sh").chmod(0o755)
    git(root, "add", "-A")
    head = commit_staged(root)
    got = {(c.old_path, c.new_path, c.status) for c in GitRepo(root, base, head).changes()}
    assert got == {("r.txt", "r2.txt", "renamed"), ("x.sh", "x.sh", "modified")}


def commit_staged(root: Path) -> str:
    git(root, "commit", "-q", "-m", "staged")
    return git(root, "rev-parse", "HEAD")


@pytest.mark.requirement("REQ-2026-010-F06")
def test_symlink_content_is_target_path(root: Path) -> None:
    (root / "real.txt").write_bytes(b"r")
    (root / "link").symlink_to("real.txt")
    git(root, "add", "-A")
    head = commit_staged(root)
    repo = GitRepo(root, head, head)
    assert repo.read("link", "head") == b"real.txt"
    assert GitRepo(root, head, "worktree").read("link", "head") == b"real.txt"


@pytest.mark.requirement("REQ-2026-010-F01")
def test_errors_are_repo_errors(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    head = commit(root, {"a": b"1"})
    with pytest.raises(RepoError):
        GitRepo(root, "no-such-ref", head)
    with pytest.raises(RepoError):
        GitRepo(root, head, "no-such-ref")
    monkeypatch.setenv("PATH", "")
    with pytest.raises(RepoError):
        GitRepo(root, head, head)


@pytest.mark.requirement("REQ-2026-010-F05")
def test_three_kinds_of_head(root: Path) -> None:
    base = commit(root, {"a": b"1"})
    (root / "a").write_bytes(b"2")
    head_commit = GitRepo(root, base, base)
    assert head_commit.changes() == []
    assert GitRepo(root, base, "worktree").changes() == [Change("a", "a", "modified")]
    assert head_commit.read("a", "head") == b"1"


@pytest.mark.requirement("REQ-2026-010-F01")
def test_unsupported_status_and_submodule(root: Path) -> None:
    sub = root.parent / (root.name + "-sub")
    sub.mkdir()
    git(sub, "init", "-q", "-b", "main")
    commit(sub, {"s": b"1"})
    base = commit(root, {"a": b"1"})
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "mod")
    head = commit_staged(root)
    repo = GitRepo(root, base, head)
    with pytest.raises(RepoError, match="submodule"):
        repo.read("mod", "head")
    with pytest.raises(RepoError, match="submodule"):
        GitRepo(root, base, "worktree").read("mod", "head")
    assert GitRepo(root, base, head).read("missing", "head") is None
