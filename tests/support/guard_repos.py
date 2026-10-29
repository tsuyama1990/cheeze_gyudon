import json
from pathlib import Path

from tests.integration.test_repo_git import git

MAIN = "main"
WORK = "feat/x"


def make_repos(tmp_path: Path) -> tuple[Path, Path]:
    """Two repos side by side: A is on main, B is on a work branch."""
    a, b = tmp_path / "A", tmp_path / "B"
    for repo, branch in ((a, MAIN), (b, WORK)):
        repo.mkdir()
        git(repo, "init", "-q", "-b", branch)
    return a, b


def bash(cwd: Path, command: str) -> str:
    return payload(cwd, "Bash", {"command": command})


def write(cwd: Path, file_path: str, tool: str = "Write") -> str:
    return payload(cwd, tool, {"file_path": file_path})


def payload(cwd: Path, tool: str, tool_input: dict[str, str]) -> str:
    return json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd)})
