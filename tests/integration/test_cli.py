from pathlib import Path

import pytest
from click.testing import CliRunner

from jtc_gov.adapters.cli import main
from tests.integration.test_repo_git import commit, git, root  # noqa: F401


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
