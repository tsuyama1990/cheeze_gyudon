import pytest

from jtc_gov.derive.git_commands import parse_git_invocations, split_segments


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.parametrize(
    ("command", "count"),
    [
        ('echo "a && b"; git commit', 2),
        ("a | b", 2),
        ("a && b || c", 3),
        ("a\nb", 2),
        ("echo 'x;y'", 1),
    ],
)
def test_segments_split_only_outside_quotes(command: str, count: int) -> None:
    """L3-U01"""
    assert len(split_segments(command)) == count


@pytest.mark.requirement("REQ-2026-011-F04")
def test_unclosed_quote_stays_one_segment_and_is_not_parsed() -> None:
    """L3-U02"""
    command = 'git commit -m "abc'
    assert split_segments(command) == [command]
    assert parse_git_invocations(command) == []


@pytest.mark.requirement("REQ-2026-011-F04")
def test_plain_commit_has_no_directory() -> None:
    """L3-U03"""
    (inv,) = parse_git_invocations("git commit -m x")
    assert (inv.subcommand, inv.directory) == ("commit", None)


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.parametrize(
    ("command", "directory"),
    [
        ("git -C /a commit", "/a"),
        ("git -C /a -C b commit", "/a/b"),
        ("git -C rel push", "rel"),
    ],
)
def test_dash_c_chains(command: str, directory: str) -> None:
    """L3-U04"""
    assert parse_git_invocations(command)[0].directory == directory


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.parametrize(
    ("command", "directory"),
    [
        ("cd A && git commit", "A"),
        ("cd A; cd ../B && git push", "B"),
        ("cd /abs && cd rel && git add -A", "/abs/rel"),
    ],
)
def test_cd_carries_into_later_segments(command: str, directory: str) -> None:
    """L3-U05"""
    assert parse_git_invocations(command)[0].directory == directory


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.requirement("REQ-2026-011-F05")
@pytest.mark.parametrize(
    "command",
    ["env X=1 git push", "command git push", "\\git push", "sudo git push", "X=1 git push"],
)
def test_leading_words_are_skipped(command: str) -> None:
    """L3-U06"""
    assert [i.subcommand for i in parse_git_invocations(command)] == ["push"]


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.parametrize(
    ("command", "subcommand"),
    [
        ("git -c user.name=x --no-pager log", "log"),
        ("git --git-dir=/g status", "status"),
        ("git -P diff", "diff"),
    ],
)
def test_options_are_skipped(command: str, subcommand: str) -> None:
    """L3-U07"""
    assert parse_git_invocations(command)[0].subcommand == subcommand


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.parametrize("command", ["echo git commit", "gitk", "cat .git/config", "", "git"])
def test_non_git_commands_yield_nothing(command: str) -> None:
    """L3-U08"""
    assert parse_git_invocations(command) == []


@pytest.mark.requirement("REQ-2026-011-F04")
@pytest.mark.requirement("REQ-2026-011-F05")
def test_several_invocations_keep_order() -> None:
    """L3-U09"""
    found = parse_git_invocations("git add a && git commit -m x && git push")
    assert [i.subcommand for i in found] == ["add", "commit", "push"]
