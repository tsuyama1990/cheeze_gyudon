from functools import partial
from pathlib import Path

import pytest

from jtc_gov.adapters.claude_hook import HookOutcome, RepoFactory, classify_git, handle
from jtc_gov.adapters.cli import run_check
from jtc_gov.domain.errors import RepoError
from jtc_gov.domain.repo import Repo
from tests.support.fake_repo import FakeRepo, with_approval

REQ = "REQ-2026-010"
TEST_FILE = (
    b'import pytest\n\n\n@pytest.mark.requirement("REQ-2026-010-F01")\n'
    b"def test_a() -> None:\n    pass\n"
)
README = {"README.md": b"r"}
APPROVED = {**README, **with_approval(REQ)}
CHANGED = {"src/a.py": b"x = 1\n", "tests/test_a.py": TEST_FILE}


def factory(base: dict[str, bytes], head: dict[str, bytes]) -> RepoFactory:
    return lambda _root, _head: FakeRepo(base, head)


def identity(repo: Repo) -> Repo:
    return repo


def factory_of(repo: Repo) -> RepoFactory:
    return lambda _root, _head: repo


def broken(exc: Exception) -> RepoFactory:
    def raise_it(_root: Path, _head: str) -> Repo:
        raise exc

    return raise_it


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / ".specs").mkdir()
    return tmp_path


def bash(command: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def write(path: str, key: str = "file_path") -> dict[str, object]:
    return {"tool_name": "Write", "tool_input": {key: path}}


@pytest.mark.requirement("REQ-2026-010-F05")
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git commit -m x", "commit"),
        ("git -C . commit", "commit"),
        ("git add . && git commit", "commit"),
        ("git commit -a", "commit"),
        ("git push origin x", "push"),
        ("command git commit", "commit"),
        ("env git push", "push"),
        ("(git commit)", "commit"),
        ("echo a\ngit commit -m x", "commit"),
        ("git push && git commit", "commit"),
        ("git push; git commit", "commit"),
        ("git commit && git push", "commit"),
        ('echo "git commit"', "commit"),
        ('bash -c "git commit"', "commit"),
        ("git stash", None),
        ("git status", None),
        ("git log --oneline", None),
        ("github commit", None),
        ("legit commit", None),
    ],
)
def test_classify_git(command: str, expected: str | None) -> None:
    assert classify_git(command) == expected


@pytest.mark.requirement("REQ-2026-010-F05")
@pytest.mark.parametrize(
    ("files", "payload", "notice"),
    [
        (APPROVED, write("src/a.py"), False),
        (README, write("src/a.py"), True),
        ({**APPROVED, **with_approval("REQ-2026-011")}, write("src/a.py"), True),
        (README, write("docs/a.md"), False),
        (README, write("/etc/passwd"), False),
        (README, write("../outside/src/a.py"), False),
        (README, write("src/a.ipynb", "notebook_path"), True),
        (README, {"tool_name": "Write"}, False),
        (README, {"tool_name": "Write", "tool_input": {}}, False),
        (README, {"tool_name": "Write", "tool_input": {"file_path": 3}}, False),
        (README, {"tool_name": "Write", "tool_input": "x"}, False),
        (README, {"tool_name": "Unknown", "tool_input": {"file_path": "src/a.py"}}, False),
        (README, {}, False),
    ],
)
def test_write_notice_never_blocks(
    root: Path, files: dict[str, bytes], payload: dict[str, object], *, notice: bool
) -> None:
    outcome = handle("pre-tool-use", payload, root, factory(files, files))
    assert outcome.exit_code == 0
    assert outcome.stderr == ""
    assert bool(outcome.stdout) is notice
    if notice:
        assert "先に承認が必要" in outcome.stdout


@pytest.mark.requirement("REQ-2026-010-F05")
@pytest.mark.parametrize(("command", "head"), [("git commit -m x", "w"), ("git push", "h")])
def test_commit_and_push_reject_violations(root: Path, command: str, head: str) -> None:
    bad = handle("pre-tool-use", bash(command), root, factory(README, {**README, **CHANGED}))
    assert bad.exit_code == 2
    assert "K.a" in bad.stderr
    good = handle("pre-tool-use", bash(command), root, factory(APPROVED, {**APPROVED, **CHANGED}))
    assert good == HookOutcome(0)


@pytest.mark.requirement("REQ-2026-010-F05")
def test_t_and_pragma_findings_only_warn(root: Path) -> None:
    pragma = {"src/a.py": b"x = 1  # pragma: no cover\n"}
    outcome = handle(
        "pre-tool-use", bash("git commit"), root, factory(APPROVED, {**APPROVED, **pragma})
    )
    assert outcome.exit_code == 0
    assert "Q.pragma" in outcome.stderr
    assert "警告" in outcome.stderr


@pytest.mark.requirement("REQ-2026-010-F05")
@pytest.mark.parametrize("exc", [RepoError("no base"), RuntimeError("boom")])
def test_infrastructure_errors_fail_open(root: Path, exc: Exception) -> None:
    git = handle("pre-tool-use", bash("git commit"), root, broken(exc))
    assert git.exit_code == 0
    assert "検査を実行できませんでした" in git.stderr
    payloads: list[dict[str, object]] = [write("src/a.py"), {"tool_name": "Read"}]
    for payload in payloads:
        assert handle("pre-tool-use", payload, root, broken(exc)) == HookOutcome(0)
    assert handle("session-start", {}, root, broken(exc)) == HookOutcome(0)


@pytest.mark.requirement("REQ-2026-010-F05")
def test_without_specs_dir(tmp_path: Path) -> None:
    for event, payload in (("session-start", {}), ("pre-tool-use", write("src/a.py"))):
        assert handle(event, payload, tmp_path, factory(README, README)) == HookOutcome(0)
    rejected = handle(
        "pre-tool-use", bash("git commit"), tmp_path, factory(README, {**README, **CHANGED})
    )
    assert rejected.exit_code == 2
    docs = handle(
        "pre-tool-use", bash("git commit"), tmp_path, factory(README, {**README, "doc/x.md": b"d"})
    )
    assert docs == HookOutcome(0)


@pytest.mark.requirement("REQ-2026-010-F05")
@pytest.mark.parametrize("event", ["session-start", "user-prompt-submit"])
def test_status_notice(root: Path, event: str) -> None:
    outcome = handle(event, {}, root, factory(APPROVED, APPROVED))
    assert outcome.exit_code == 0
    assert len(outcome.stdout.splitlines()) <= 3
    assert "要件 1 件" in outcome.stdout


@pytest.mark.requirement("REQ-2026-010-F05")
def test_unknown_event_does_nothing(root: Path) -> None:
    assert handle(
        "stop", bash("git commit"), root, factory(README, {**README, **CHANGED})
    ) == HookOutcome(0)


@pytest.mark.requirement("REQ-2026-010-F05")
def test_hook_and_ci_entry_agree_on_k() -> None:
    """L1-I01: the same repo state gives the same K verdict at both entries."""
    for base, head in ((README, {**README, **CHANGED}), (APPROVED, {**APPROVED, **CHANGED})):
        fake = FakeRepo(base, head)
        code, output = run_check(partial(identity, fake), as_json=False)
        hook = handle("pre-tool-use", bash("git commit"), Path("/nonexistent"), factory_of(fake))
        # /nonexistent has no .specs but a git command is always checked
        assert (code == 1) == (hook.exit_code == 2)
        assert ("K.a" in output) == ("K.a" in hook.stderr)
