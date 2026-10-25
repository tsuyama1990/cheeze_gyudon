import json
from typing import Any

from jtc_gov.domain.exceptions import UnauthorizedFileAccessError
from jtc_gov.services.state_engine import is_path_unlocked, read_state


def verify_tool(tool_name: str, input_json: str) -> None:
    """
    High-speed verifier for Claude PreToolUse hook.
    Inspects if the requested tool modification is authorized by the current active state.
    """
    if tool_name not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        # We only care about tools that modify files
        return

    try:
        payload: dict[str, Any] = json.loads(input_json)
    except json.JSONDecodeError:
        # If payload is invalid json, let the tool execution fail naturally or reject it
        msg = "Tool payload is not valid JSON."
        raise UnauthorizedFileAccessError(msg) from None

    # Determine the target path depending on the exact tool spec.
    # We will assume a common property like `path` or `file_path`.
    target_path = (
        payload.get("path")
        or payload.get("file_path")
        or payload.get("filepath")
        or payload.get("notebook_path")
    )
    if not target_path:
        # Cannot determine target path, maybe log it, but reject by default for safety
        msg = "Could not determine file path from tool payload."
        raise UnauthorizedFileAccessError(msg)

    state = read_state()
    active_req_id = state.active_requirement_id
    if active_req_id not in state.requirements:
        msg = f"Active requirement '{active_req_id}' not found in state."
        raise UnauthorizedFileAccessError(msg)

    active_req = state.requirements[active_req_id]

    if not is_path_unlocked(target_path, active_req.unlocked_paths):
        msg = (
            f"Access denied: '{target_path}' is locked. "
            f"Editing is blocked in {active_req.current_gate.value}. "
            "Complete the preceding gates and get human sign-off first."
        )
        raise UnauthorizedFileAccessError(msg)
