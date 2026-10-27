import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.adapters.cli import main
from tests.integration.test_repo_git import commit, git, root  # noqa: F401


@pytest.mark.spec("L2-I25", "L2-I26", "L2-I27")
@pytest.mark.requirement("REQ-2026-010-F01")
def test_check_and_status_in_a_real_repo(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = commit(root, {"README.md": b"x"})
    monkeypatch.chdir(root)
    runner = CliRunner()
    ok = runner.invoke(main, ["check", "--base", base])
    assert ok.exit_code == 0
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_a(): pass\n")
    bad = runner.invoke(main, ["check", "--base", base])
    assert bad.exit_code == 1
    assert "K.a" in bad.output
    as_json = runner.invoke(main, ["check", "--base", base, "--json"])
    assert '"ok": false' in as_json.output
    missing = runner.invoke(main, ["check", "--base", "no-such-ref"])
    assert missing.exit_code == 2
    assert "E.repo" in missing.output
    status = runner.invoke(main, ["status", "--base", base])
    assert status.exit_code == 0
    assert "要件なし" in status.output
    assert runner.invoke(main, ["status", "--base", "no-such-ref"]).exit_code == 2


@pytest.mark.requirement("REQ-2026-010-F01")
def test_outside_a_git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["check"])
    assert result.exit_code == 2
    assert "E.repo" in result.output


@pytest.mark.requirement("REQ-2026-010-F06")
def test_status_internal_error_exits_2(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = commit(root, {"README.md": b"x"})
    monkeypatch.chdir(root)

    def boom(*_: object) -> str:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr("jtc_gov.adapters.cli.format_status", boom)
    result = CliRunner().invoke(main, ["status", "--base", base])
    assert result.exit_code == 2
    assert "E.internal" in result.output


@pytest.mark.requirement("REQ-2026-010-F06")
@pytest.mark.spec("L2-I28")
def test_status_and_check_do_not_write_anything(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = commit(root, {"README.md": b"x"})
    monkeypatch.chdir(root)
    before = (git(root, "status", "--porcelain"), sorted(p.name for p in root.iterdir()))
    for command in ("status", "check"):
        CliRunner().invoke(main, [command, "--base", base])
    after = (git(root, "status", "--porcelain"), sorted(p.name for p in root.iterdir()))
    assert before == after
    assert not list(root.rglob("state.json"))


@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.spec("L2-I27")
def test_check_defaults_to_origin_main(
    root: Path,  # noqa: F811
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote = tmp_path_factory.mktemp("remote")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)  # noqa: S603, S607
    commit(root, {"README.md": b"x"})
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    monkeypatch.chdir(root)
    clean = CliRunner().invoke(main, ["check"])
    assert (clean.exit_code, clean.output) == (0, "")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_a(): pass\n")
    assert CliRunner().invoke(main, ["check"]).exit_code == 1


@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.spec("L2-I25")
def test_missing_git_is_an_unevaluated_check(
    root: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit(root, {"README.md": b"x"})
    monkeypatch.chdir(root)
    monkeypatch.setenv("PATH", "")
    result = CliRunner().invoke(main, ["check", "--base", "main"])
    assert result.exit_code == 2
    assert "E.repo" in result.output
