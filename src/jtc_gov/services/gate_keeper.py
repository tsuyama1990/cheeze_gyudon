import json
from pathlib import Path

from jtc_gov.domain.exceptions import GateCheckFailedError
from jtc_gov.domain.models import GateId, GateReviewDeliverable, StateModel
from jtc_gov.services.state_engine import read_state, write_state


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
            if review.gate_id == gate_id and review.status != "APPROVED":
                msg = f"Review {review_file.name} is not APPROVED (status: {review.status})"
                raise GateCheckFailedError(msg)
        except Exception as e:
            msg = f"Failed to parse review {review_file}: {e}"
            raise GateCheckFailedError(msg) from e


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


def validate_gate(gate_id: GateId) -> None:
    """
    Validates that the mandatory design/test pairs exist and all required
    persona JSON reviews are APPROVED. Advances the gate if successful.
    """
    state = read_state()
    active_req_id = state.active_requirement_id

    if active_req_id not in state.requirements:
        msg = f"Active requirement '{active_req_id}' not found."
        raise GateCheckFailedError(msg)

    active_req = state.requirements[active_req_id]

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

    # 4. Advance State
    gate_sequence = [
        GateId.GATE1_SPEC,
        GateId.GATE2_SYSTEM,
        GateId.GATE3_INTEGRATION,
        GateId.GATE4_DETAIL,
        GateId.GATE5_IMPL
    ]

    current_idx = gate_sequence.index(gate_id)

    new_completed = list(active_req.completed_gates)
    if gate_id not in new_completed:
        new_completed.append(gate_id)

    next_gate = gate_sequence[current_idx + 1] if current_idx + 1 < len(gate_sequence) else gate_id

    # Unlock paths for next gate
    next_unlocked_paths = get_unlocked_paths_for_gate(next_gate, active_req_id)

    # Update requirement item
    req_dict = active_req.model_dump()
    req_dict["current_gate"] = next_gate
    req_dict["completed_gates"] = new_completed
    req_dict["unlocked_paths"] = next_unlocked_paths
    if next_gate == GateId.GATE5_IMPL and gate_id == GateId.GATE5_IMPL:
         req_dict["status"] = "COMPLETED"

    # Update state
    state_dict = state.model_dump()
    state_dict["requirements"][active_req_id] = req_dict

    new_state = StateModel.model_validate(state_dict)
    write_state(new_state)


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


def get_unlocked_paths_for_gate(gate_id: GateId, active_req_id: str) -> list[str]:
    """Returns standard unlocked paths for a given gate."""
    base_paths = [
        ".agent/*", "doc/*", "README.md", "pyproject.toml",
        ".pre-commit-config.yaml", "scripts/*"
    ]
    if gate_id == GateId.GATE1_SPEC:
        return [*base_paths, f".specs/{active_req_id}/01_*"]
    if gate_id == GateId.GATE2_SYSTEM:
        return [*base_paths, f".specs/{active_req_id}/02_*"]
    if gate_id == GateId.GATE3_INTEGRATION:
        return [*base_paths, f".specs/{active_req_id}/03_*"]
    if gate_id == GateId.GATE4_DETAIL:
        return [*base_paths, f".specs/{active_req_id}/04_*", f".specs/{active_req_id}/05_*", "tests/*"]
    if gate_id == GateId.GATE5_IMPL:
        # Full unlock for implementation
        return [*base_paths, f".specs/{active_req_id}/*", "tests/*", "src/*"]
    return base_paths
