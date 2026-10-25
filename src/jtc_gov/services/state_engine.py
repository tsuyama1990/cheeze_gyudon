import fnmatch
import json
from pathlib import Path, PurePosixPath
from typing import Any

from jtc_gov.domain.exceptions import StateCorruptedError, StateNotFoundError
from jtc_gov.domain.models import RequirementItem, StateModel


def get_state_path() -> Path:
    """Returns the path to the state.json file."""
    # Assuming execution from repo root
    return Path(".specs/state.json")


def read_state() -> StateModel:
    """Reads the state from .specs/state.json and returns a StateModel instance."""
    state_path = get_state_path()
    if not state_path.exists():
        msg = f"State file not found at {state_path}"
        raise StateNotFoundError(msg)

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
        temp_path.replace(state_path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        msg = f"Failed to write state file: {e}"
        raise StateCorruptedError(msg) from e


def get_active_requirement(state: StateModel, error_type: type[Exception]) -> RequirementItem:
    """Returns the active requirement, raising error_type if state does not contain it."""
    if state.active_requirement_id not in state.requirements:
        msg = f"Active requirement '{state.active_requirement_id}' not found in state."
        raise error_type(msg)
    return state.requirements[state.active_requirement_id]


def update_requirement(state: StateModel, req_id: str, **changes: Any) -> StateModel:  # noqa: ANN401
    """Returns a validated copy of state with the given fields of one requirement replaced."""
    data = state.model_dump()
    data["requirements"][req_id].update(changes)
    return StateModel.model_validate(data)


def _to_root_relative(target_path: str) -> str | None:
    """
    Resolves target_path against the current working directory and returns it as a
    root-relative POSIX path. Returns None when the path escapes the project root.
    """
    root = Path.cwd().resolve()
    candidate = Path(target_path.replace("\\", "/"))
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return None
    return PurePosixPath(relative).as_posix()


def is_path_unlocked(target_path: str, unlocked_paths: list[str]) -> bool:
    """
    Checks if target_path matches any of the glob patterns in unlocked_paths.
    Paths outside the project root are always denied.
    """
    relative = _to_root_relative(target_path)
    if relative is None:
        return False
    return any(fnmatch.fnmatch(relative, pattern) for pattern in unlocked_paths)
