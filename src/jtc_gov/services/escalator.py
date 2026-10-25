import json
from datetime import UTC, datetime
from pathlib import Path

from jtc_gov.domain.models import GateId, RequirementStatus
from jtc_gov.services.gate_keeper import get_unlocked_paths_for_gate
from jtc_gov.services.state_engine import (
    get_active_requirement,
    read_state,
    update_requirement,
    write_state,
)


def _write_escalation_record(
    active_req_id: str, from_gate: GateId, to_gate: GateId, reason: str
) -> None:
    esc_dir = Path(f".specs/{active_req_id}/escalations")
    esc_dir.mkdir(parents=True, exist_ok=True)

    esc_count = len(list(esc_dir.glob("ESC-*.json"))) + 1
    esc_file = esc_dir / f"ESC-{esc_count:03d}.json"

    esc_record = {
        "escalation_id": f"ESC-{esc_count:03d}",
        "requirement_id": active_req_id,
        "from_gate": from_gate.value,
        "to_gate": to_gate.value,
        "reason": reason,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    esc_file.write_text(json.dumps(esc_record, indent=2), encoding="utf-8")


def escalate(to_gate: int, reason: str) -> None:
    """
    Safely rolls back state and workspace lock to a previous gate.
    Creates an ESC-NNN.json escalation record.
    """
    state = read_state()
    active_req_id = state.active_requirement_id

    active_req = get_active_requirement(state, ValueError)

    gate_sequence = list(GateId)
    if not 1 <= to_gate <= len(gate_sequence):
        msg = "Invalid target gate for escalation. Must be 1-5."
        raise ValueError(msg)

    target_gate = gate_sequence[to_gate - 1]
    current_idx = gate_sequence.index(active_req.current_gate)
    target_idx = to_gate - 1

    if target_idx >= current_idx:
        msg = "Escalation must be to a previous gate."
        raise ValueError(msg)

    # Completed gates ahead of the target gate are revoked
    new_state = update_requirement(
        state,
        active_req_id,
        current_gate=target_gate,
        status=RequirementStatus.ROLLBACK,
        unlocked_paths=get_unlocked_paths_for_gate(target_gate, active_req_id),
        completed_gates=[
            g for g in active_req.completed_gates if gate_sequence.index(g) < target_idx
        ],
    )
    _write_escalation_record(active_req_id, active_req.current_gate, target_gate, reason)

    write_state(new_state)
