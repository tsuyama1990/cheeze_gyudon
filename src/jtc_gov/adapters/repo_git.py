import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

from jtc_gov.domain.errors import RepoError
from jtc_gov.domain.models import Change, Ref, Status

WORKTREE = "worktree"
_GITLINK_MODE = b"160000"
_STATUS: dict[str, Status] = {"A": "added", "M": "modified", "T": "modified", "D": "deleted"}


class GitRepo:
    def __init__(self, root: Path, base: str, head: str) -> None:
        self._root = root
        self._rev: dict[Ref, str] = {"base": base, "head": head}
        for rev in (base, head):
            if rev != WORKTREE:
                self._git("rev-parse", "--verify", f"{rev}^{{commit}}")

    def _run(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        cmd = ["git", "-C", str(self._root), "-c", "core.quotepath=off", *args]
        try:
            return subprocess.run(cmd, capture_output=True, check=False)  # noqa: S603
        except OSError as e:
            raise RepoError(str(e)) from e

    def _git(self, *args: str) -> bytes:
        done = self._run(*args)
        if done.returncode != 0:
            raise RepoError(done.stderr.decode(errors="replace").strip())
        return done.stdout

    def _names(self, *args: str) -> list[str]:
        return [n.decode() for n in self._git(*args).split(b"\0") if n]

    def read(self, path: str, ref: Ref) -> bytes | None:
        rev = self._rev[ref]
        if rev == WORKTREE:
            return self._read_worktree(path)
        entry = self._git("ls-tree", rev, "--", path).split()
        if not entry:
            return None
        if entry[0] == _GITLINK_MODE:
            msg = f"submodule is not supported: {path}"
            raise RepoError(msg)
        return self._git("show", f"{rev}:{path}")

    def _read_worktree(self, path: str) -> bytes | None:
        if path not in self.list("head"):
            return None
        full = self._root / path
        if full.is_symlink():
            return os.fsencode(full.readlink())
        if full.is_dir():
            msg = f"submodule is not supported: {path}"
            raise RepoError(msg)
        return full.read_bytes()

    def list(self, ref: Ref) -> Sequence[str]:
        rev = self._rev[ref]
        if rev != WORKTREE:
            return sorted(self._names("ls-tree", "-r", "--name-only", "-z", rev))
        present = self._names("ls-files", "-z", "-c", "-o", "--exclude-standard")
        deleted = set(self._names("ls-files", "-z", "-d"))
        return sorted(set(present) - deleted)

    def changes(self) -> Sequence[Change]:
        base, head = self._rev["base"], self._rev["head"]
        revs = (base,) if head == WORKTREE else (base, head)
        tokens = self._names("diff", "-M", "--name-status", "-z", *revs)
        out: list[Change] = []
        i = 0
        while i < len(tokens):
            code = tokens[i][0]
            if code == "R":
                out.append(Change(tokens[i + 1], tokens[i + 2], "renamed"))
                i += 3
            elif code in _STATUS:
                path = tokens[i + 1]
                status = _STATUS[code]
                out.append(
                    Change(
                        None if status == "added" else path,
                        None if status == "deleted" else path,
                        status,
                    )
                )
                i += 2
            else:
                msg = f"unsupported status: {tokens[i]}"
                raise RepoError(msg)
        if head == WORKTREE:
            untracked = self._names("ls-files", "-z", "-o", "--exclude-standard")
            out += [Change(None, p, "added") for p in untracked]
        return out
