import json
from pathlib import Path

import pytest

from jtc_gov.adapters.agy_hook import to_call, to_outcome
from jtc_gov.adapters.global_hook import Decision, ToolCall, claude_call, decide_call

WORKSPACE = "/w"
POINTER = Path(__file__).parents[2] / "AGENTS.md"


def payload(name: str, args: object, workspaces: object = None) -> dict[str, object]:
    return {
        "toolCall": {"name": name, "args": args},
        "workspacePaths": [WORKSPACE] if workspaces is None else workspaces,
    }


@pytest.mark.requirement("REQ-2026-012-F01")
@pytest.mark.parametrize(
    ("args", "cwd"),
    [
        ({"CommandLine": "ls", "Cwd": "/abs/dir"}, "/abs/dir"),
        ({"CommandLine": "ls", "Cwd": "rel"}, "/w/rel"),
        ({"CommandLine": "ls"}, "/w"),
    ],
)
def test_run_command_cwd(args: dict[str, str], cwd: str) -> None:
    """L3-U01"""
    assert to_call(payload("run_command", args)) == ToolCall(cwd, command="ls")


@pytest.mark.requirement("REQ-2026-012-F01")
@pytest.mark.parametrize(
    ("tool", "key"),
    [
        ("write_to_file", "TargetFile"),
        ("replace_file_content", "TargetFile"),
        ("multi_replace_file_content", "TargetFile"),
        ("write_file", "Path"),
        ("edit_file", "Path"),
    ],
)
def test_write_tools_carry_a_path(tool: str, key: str) -> None:
    """L3-U02"""
    assert to_call(payload(tool, {key: "src/a.py"})) == ToolCall(WORKSPACE, path="src/a.py")


@pytest.mark.requirement("REQ-2026-012-F01")
@pytest.mark.parametrize("tool", ["view_file", "grep_search", "list_dir"])
def test_other_tools_are_not_judged(tool: str) -> None:
    """L3-U03"""
    assert to_call(payload(tool, {"Path": "x"})) is None


@pytest.mark.requirement("REQ-2026-012-F01")
@pytest.mark.parametrize(
    "broken",
    [
        {"workspacePaths": ["/w"]},
        {"toolCall": {"name": 1, "args": {}}, "workspacePaths": ["/w"]},
        payload("run_command", ["ls"]),
        payload("run_command", {"CommandLine": 1}),
        payload("write_file", {"Path": 1}),
        payload("run_command", {"CommandLine": "ls"}, workspaces=[]),
        payload("run_command", {"CommandLine": "ls"}, workspaces=[1]),
        payload("run_command", {"CommandLine": "ls"}, workspaces="/w"),
    ],
)
def test_broken_input_is_not_judged(broken: dict[str, object]) -> None:
    """L3-U04"""
    assert to_call(broken) is None


@pytest.mark.requirement("REQ-2026-012-F01")
def test_outcome_shapes() -> None:
    """L3-U05"""
    for kind in ("deny", "ask"):
        out = to_outcome(Decision(kind, "reason"))
        assert out.exit_code == 0
        assert json.loads(out.stdout) == {"decision": kind, "reason": "reason"}
    allowed = to_outcome(Decision("allow"))
    assert (allowed.exit_code, allowed.stdout, allowed.stderr) == (0, "", "")


@pytest.mark.requirement("REQ-2026-012-F01")
def test_japanese_reason_is_not_escaped() -> None:
    """L3-U06"""
    assert "禁止" in to_outcome(Decision("deny", "直接のコミットは禁止です")).stdout


@pytest.mark.requirement("REQ-2026-012-F02")
def test_empty_call_is_allowed() -> None:
    """L3-U07"""
    assert decide_call(ToolCall("/w")).kind == "allow"


@pytest.mark.requirement("REQ-2026-012-F02")
@pytest.mark.parametrize(
    ("payload_", "expected"),
    [
        (
            {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": "/w"},
            ToolCall("/w", command="ls"),
        ),
        (
            {"tool_name": "Write", "tool_input": {"file_path": "a"}, "cwd": "/w"},
            ToolCall("/w", path="a"),
        ),
        ({"tool_name": "Read", "tool_input": {"file_path": "a"}, "cwd": "/w"}, None),
        ({"tool_name": "Bash", "tool_input": {"command": "ls"}}, None),
    ],
)
def test_claude_call(payload_: dict[str, object], expected: ToolCall | None) -> None:
    """L3-U08"""
    assert claude_call(payload_) == expected


@pytest.mark.requirement("REQ-2026-012-F03")
def test_agents_md_is_a_one_line_pointer() -> None:
    """L3-U09"""
    text = POINTER.read_text(encoding="utf-8")
    assert "(AGENT.md)" in text
    assert len([line for line in text.splitlines() if line.strip()]) == 2
