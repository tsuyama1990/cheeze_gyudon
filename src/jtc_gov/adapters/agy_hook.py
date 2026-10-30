import json
import posixpath
import sys
from typing import Final, NoReturn

from jtc_gov.adapters.claude_hook import HookOutcome
from jtc_gov.adapters.global_hook import Decision, ToolCall, decide_call, emit

EVENTS: Final = ("agy-pre-tool-use",)
COMMAND_TOOL: Final = "run_command"
COMMAND_KEY: Final = "CommandLine"
CWD_KEY: Final = "Cwd"
PATH_KEYS: Final = {
    "write_to_file": "TargetFile",
    "replace_file_content": "TargetFile",
    "multi_replace_file_content": "TargetFile",
    "write_file": "Path",
    "edit_file": "Path",
}


def to_call(payload: dict[str, object]) -> ToolCall | None:
    tool_call, workspaces = payload.get("toolCall"), payload.get("workspacePaths")
    if not isinstance(tool_call, dict) or not isinstance(workspaces, list) or not workspaces:
        return None
    name, args, base = tool_call.get("name"), tool_call.get("args"), workspaces[0]
    if not isinstance(name, str) or not isinstance(args, dict) or not isinstance(base, str):
        return None
    if name == COMMAND_TOOL:
        command, cwd = args.get(COMMAND_KEY), args.get(CWD_KEY)
        if not isinstance(command, str):
            return None
        return ToolCall(
            posixpath.join(base, cwd) if isinstance(cwd, str) else base, command=command
        )
    path = args.get(PATH_KEYS.get(name, ""))
    return ToolCall(base, path=path) if isinstance(path, str) else None


def to_outcome(decision: Decision) -> HookOutcome:
    if decision.kind == "allow":
        return HookOutcome(0)
    output = {"decision": decision.kind, "reason": decision.reason}
    return HookOutcome(0, stdout=json.dumps(output, ensure_ascii=False))


def main(event: str) -> NoReturn:
    outcome = HookOutcome(0)
    try:
        payload = json.loads(sys.stdin.read())
        call = to_call(payload) if event in EVENTS and isinstance(payload, dict) else None
        if call is not None:
            outcome = to_outcome(decide_call(call))
    except Exception:  # noqa: BLE001 - the hook is advisory (DEC-002)
        outcome = HookOutcome(0)
    emit(outcome)
