import posixpath
import re
import shlex
from dataclasses import dataclass
from typing import Final

SEGMENT_SEPARATORS: Final = ("&&", "||", ";", "|", "\n")
WRAPPER_WORDS: Final = frozenset({"env", "command", "sudo"})
OPTIONS_WITH_VALUE: Final = ("-C", "-c", "--git-dir", "--work-tree", "--namespace")
ASSIGNMENT: Final = re.compile(r"[A-Za-z_]\w*=")
CHANGE_DIRECTORY: Final = "cd"
GIT: Final = "git"
DIRECTORY_OPTION: Final = "-C"
QUOTES: Final = "'\""


@dataclass(frozen=True)
class GitInvocation:
    subcommand: str
    args: tuple[str, ...]
    directory: str | None


def split_segments(command: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    quote = ""
    i = 0
    while i < len(command):
        ch = command[i]
        separator = next((s for s in SEGMENT_SEPARATORS if command.startswith(s, i)), "")
        if ch == "\\" and quote != "'" and i + 1 < len(command):
            current.append(command[i : i + 2])
            i += 2
        elif quote:
            quote = "" if ch == quote else quote
            current.append(ch)
            i += 1
        elif ch in QUOTES:
            quote = ch
            current.append(ch)
            i += 1
        elif separator:
            segments.append("".join(current))
            current = []
            i += len(separator)
        else:
            current.append(ch)
            i += 1
    segments.append("".join(current))
    return [s for s in segments if s.strip()]


def _skip_prefix(tokens: list[str]) -> list[str]:
    i = 0
    while i < len(tokens) and (tokens[i] in WRAPPER_WORDS or ASSIGNMENT.match(tokens[i])):
        i += 1
    return tokens[i:]


def _parse_git(tokens: list[str], current: str | None) -> GitInvocation | None:
    directory = current
    i = 1
    while i < len(tokens) and tokens[i].startswith("-"):
        token = tokens[i]
        if token in OPTIONS_WITH_VALUE and i + 1 < len(tokens):
            if token == DIRECTORY_OPTION:
                value = tokens[i + 1]
                directory = posixpath.join(directory, value) if directory else value
            i += 2
        else:
            i += 1
    if i >= len(tokens):
        return None
    return GitInvocation(tokens[i], tuple(tokens[i + 1 :]), directory)


def parse_git_invocations(command: str) -> list[GitInvocation]:
    found: list[GitInvocation] = []
    current: str | None = None
    for segment in split_segments(command):
        try:
            tokens = _skip_prefix(shlex.split(segment))
        except ValueError:
            continue
        if not tokens:
            continue
        if tokens[0] == CHANGE_DIRECTORY:
            if len(tokens) > 1:
                current = posixpath.normpath(posixpath.join(current or "", tokens[1]))
        elif tokens[0] == GIT:
            invocation = _parse_git(tokens, current)
            if invocation is not None:
                found.append(invocation)
    return found
