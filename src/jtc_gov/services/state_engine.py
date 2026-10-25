import fnmatch
import json
import os
from pathlib import Path

from jtc_gov.domain.exceptions import StateCorruptedError
from jtc_gov.domain.models import StateModel


def get_state_path() -> Path:
    """Returns the path to the state.json file."""
    # Assuming execution from repo root
    return Path(".specs/state.json")


def read_state() -> StateModel:
    """Reads the state from .specs/state.json and returns a StateModel instance."""
    state_path = get_state_path()
    if not state_path.exists():
        msg = f"State file not found at {state_path}"
        raise StateCorruptedError(msg)

    try:
        content = state_path.read_text(encoding="utf-8")
        data = json.loads(content)
        return StateModel.model_validate(data)
    except Exception as e:
        msg = f"Failed to parse state file: {e}"
        raise StateCorruptedError(msg) from e


def write_state(state: StateModel) -> None:
    """Atomically writes the StateModel to .specs/state.json."""
    state_path = get_state_path()
    temp_path = state_path.with_suffix(".json.tmp")

    try:
        # Pydantic v2 model_dump_json for serialization
        json_data = state.model_dump_json(indent=2)
        temp_path.write_text(json_data, encoding="utf-8")
        # Atomic replacement (POSIX compliant, generally works on Windows in newer Pythons)
        os.replace(temp_path, state_path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        msg = f"Failed to write state file: {e}"
        raise StateCorruptedError(msg) from e


def is_path_unlocked(target_path: str, unlocked_paths: list[str]) -> bool:
    """
    Checks if target_path matches any of the glob patterns in unlocked_paths.
    Matches using fnmatch.
    """
    return any(fnmatch.fnmatch(target_path, pattern) for pattern in unlocked_paths)
