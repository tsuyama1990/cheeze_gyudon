import json
from datetime import UTC, datetime
from pathlib import Path

from jtc_gov.domain.models import GateId, StateModel
from jtc_gov.services.gate_keeper import get_unlocked_paths_for_gate
from jtc_gov.services.state_engine import read_state, write_state


def escalate(to_gate: int, reason: str) -> None:
    """
    Safely rolls back state and workspace lock to a previous gate.
    Creates an ESC-NNN.json escalation record.
    """
    state = read_state()
    active_req_id = state.active_requirement_id

    if active_req_id not in state.requirements:
        msg = f"Active requirement '{active_req_id}' not found."
        raise ValueError(msg)

    active_req = state.requirements[active_req_id]

    gate_mapping = {
        1: GateId.GATE1_SPEC,
        2: GateId.GATE2_SYSTEM,
        3: GateId.GATE3_INTEGRATION,
        4: GateId.GATE4_DETAIL,
        5: GateId.GATE5_IMPL
    }

    if to_gate not in gate_mapping:
        msg = "Invalid target gate for escalation. Must be 1-5."
        raise ValueError(msg)

    target_gate = gate_mapping[to_gate]

    gate_sequence = [
        GateId.GATE1_SPEC,
        GateId.GATE2_SYSTEM,
        GateId.GATE3_INTEGRATION,
        GateId.GATE4_DETAIL,
        GateId.GATE5_IMPL
    ]

    current_idx = gate_sequence.index(active_req.current_gate)
    target_idx = gate_sequence.index(target_gate)

    if target_idx >= current_idx:
        msg = "Escalation must be to a previous gate."
        raise ValueError(msg)

    # Update requirement item
    req_dict = active_req.model_dump()
    req_dict["current_gate"] = target_gate
    req_dict["status"] = "ROLLBACK"
    req_dict["unlocked_paths"] = get_unlocked_paths_for_gate(target_gate, active_req_id)

    # Remove completed gates that are ahead of the target gate
    new_completed = [g for g in active_req.completed_gates if gate_sequence.index(g) < target_idx]
    req_dict["completed_gates"] = new_completed

    state_dict = state.model_dump()
    state_dict["requirements"][active_req_id] = req_dict

    new_state = StateModel.model_validate(state_dict)

    # Generate escalation record
    esc_dir = Path(f".specs/{active_req_id}/escalations")
    esc_dir.mkdir(parents=True, exist_ok=True)

    esc_count = len(list(esc_dir.glob("ESC-*.json"))) + 1
    esc_file = esc_dir / f"ESC-{esc_count:03d}.json"

    esc_record = {
        "escalation_id": f"ESC-{esc_count:03d}",
        "requirement_id": active_req_id,
        "from_gate": active_req.current_gate.value,
        "to_gate": target_gate.value,
        "reason": reason,
        "timestamp": datetime.now(UTC).isoformat()
    }

    esc_file.write_text(json.dumps(esc_record, indent=2), encoding="utf-8")

    write_state(new_state)
