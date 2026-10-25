import json
from pathlib import Path
from typing import Any

from jtc_gov.domain.exceptions import GateCheckFailedError
from jtc_gov.domain.models import GateId, GateReviewDeliverable, RequirementStatus, StateModel
from jtc_gov.services.state_engine import (
    get_active_requirement,
    read_state,
    update_requirement,
    write_state,
)


def _validate_pair_deliverables(gate_id: GateId, spec_dir: Path) -> None:
    pairs = get_required_pairs(gate_id)
    for pair_item in pairs:
        matches = list(spec_dir.glob(pair_item))
        if not matches and "test" in pair_item.lower():
            matches = list(Path("tests").glob(pair_item))
            if not matches and pair_item.startswith("tests/"):
                matches = list(Path().glob(pair_item))

        if not matches:
            msg = f"Missing mandatory pair deliverable matching: {pair_item}"
            raise GateCheckFailedError(msg)


def _validate_reviews(gate_id: GateId, spec_dir: Path) -> None:
    review_dir = spec_dir / "reviews"
    if not review_dir.exists():
        return

    for review_file in review_dir.glob("*.json"):
        try:
            data = json.loads(review_file.read_text(encoding="utf-8"))
            review = GateReviewDeliverable.model_validate(data)
        except Exception as e:
            msg = f"Failed to parse review {review_file}: {e}"
            raise GateCheckFailedError(msg) from e
        if review.gate_id == gate_id and review.status != "APPROVED":
            msg = f"Review {review_file.name} is not APPROVED (status: {review.status})"
            raise GateCheckFailedError(msg)


def _validate_human_signoff(gate_id: GateId, spec_dir: Path) -> None:
    if gate_id == GateId.GATE4_DETAIL:
        decision_file = spec_dir / "05_decision.md"
        if not decision_file.exists():
            msg = "Missing 05_decision.md for Gate 4 human sign-off."
            raise GateCheckFailedError(msg)
        content = decision_file.read_text(encoding="utf-8")
        if "HUMAN_SIGN_OFF: APPROVED" not in content:
            msg = "Missing 'HUMAN_SIGN_OFF: APPROVED' in 05_decision.md."
            raise GateCheckFailedError(msg)


def _advance_state(state: StateModel, active_req_id: str, gate_id: GateId) -> None:
    active_req = state.requirements[active_req_id]
    gate_sequence = list(GateId)
    current_idx = gate_sequence.index(gate_id)

    new_completed = list(active_req.completed_gates)
    if gate_id not in new_completed:
        new_completed.append(gate_id)

    next_gate = gate_sequence[current_idx + 1] if current_idx + 1 < len(gate_sequence) else gate_id

    # Unlock paths for next gate
    next_unlocked_paths = get_unlocked_paths_for_gate(next_gate, active_req_id)

    changes: dict[str, Any] = {
        "current_gate": next_gate,
        "completed_gates": new_completed,
        "unlocked_paths": next_unlocked_paths,
    }
    if gate_id == GateId.GATE5_IMPL:
        changes["status"] = RequirementStatus.COMPLETED
    write_state(update_requirement(state, active_req_id, **changes))


def validate_gate(gate_id: GateId) -> None:
    """
    Validates that the mandatory design/test pairs exist and all required
    persona JSON reviews are APPROVED. Advances the gate if successful.
    """
    state = read_state()
    active_req_id = state.active_requirement_id

    active_req = get_active_requirement(state, GateCheckFailedError)

    if active_req.current_gate != gate_id:
        msg = f"Cannot validate {gate_id.value}: current gate is {active_req.current_gate.value}"
        raise GateCheckFailedError(msg)

    spec_dir = Path(f".specs/{active_req_id}")
    if not spec_dir.exists():
        msg = f"Spec directory {spec_dir} not found."
        raise GateCheckFailedError(msg)

    _validate_pair_deliverables(gate_id, spec_dir)
    _validate_reviews(gate_id, spec_dir)
    _validate_human_signoff(gate_id, spec_dir)

    _advance_state(state, active_req_id, gate_id)


def get_required_pairs(gate_id: GateId) -> list[str]:
    """Returns required file globs for a given gate."""
    if gate_id == GateId.GATE1_SPEC:
        return ["01_req_spec.md", "01_acceptance_tests.feature"]
    if gate_id == GateId.GATE2_SYSTEM:
        return ["02_system_design.md", "02_system_tests.md"]
    if gate_id == GateId.GATE3_INTEGRATION:
        return ["03_architecture.md", "03_integration_tests.md"]
    if gate_id == GateId.GATE4_DETAIL:
        return ["04_detail_design.md", "tests/test_*.py"]
    return []


GATE_UNLOCK_PATTERNS: dict[GateId, list[str]] = {
    GateId.GATE1_SPEC: [".specs/{req}/01_*"],
    GateId.GATE2_SYSTEM: [".specs/{req}/02_*"],
    GateId.GATE3_INTEGRATION: [".specs/{req}/03_*"],
    GateId.GATE4_DETAIL: [".specs/{req}/04_*", ".specs/{req}/05_*", "tests/*"],
    GateId.GATE5_IMPL: [".specs/{req}/*", "tests/*", "src/*"],
}

BASE_UNLOCKED_PATHS = [
    ".agent/*",
    "doc/*",
    "README.md",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "scripts/*",
]


def get_unlocked_paths_for_gate(gate_id: GateId, active_req_id: str) -> list[str]:
    """Returns standard unlocked paths for a given gate."""
    gate_paths = [p.format(req=active_req_id) for p in GATE_UNLOCK_PATTERNS[gate_id]]
    return [*BASE_UNLOCKED_PATHS, *gate_paths]
