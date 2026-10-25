from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class GateId(StrEnum):
    GATE1_SPEC = "GATE1_SPEC"
    GATE2_SYSTEM = "GATE2_SYSTEM"
    GATE3_INTEGRATION = "GATE3_INTEGRATION"
    GATE4_DETAIL = "GATE4_DETAIL"
    GATE5_IMPL = "GATE5_IMPL"


class RequirementStatus(StrEnum):
    INIT = "INIT"
    IN_PROGRESS = "IN_PROGRESS"
    ROLLBACK = "ROLLBACK"
    COMPLETED = "COMPLETED"


class RequirementItem(BaseModel):
    title: str = Field(strict=True)
    current_gate: GateId = Field(strict=False)
    status: RequirementStatus = Field(strict=False)
    unlocked_paths: list[str] = Field(strict=True, default_factory=list)
    completed_gates: list[GateId] = Field(default_factory=list) # pyright: ignore

    model_config = {"frozen": True}


class StateModel(BaseModel):
    active_requirement_id: str = Field(strict=True)
    requirements: dict[str, RequirementItem] = Field(strict=False, default_factory=dict)

    model_config = {"frozen": True}


class GateReviewDeliverable(BaseModel):
    gate_id: GateId = Field(strict=False)
    requirement_id: str = Field(strict=True, pattern=r"^REQ-\d{4}-\d{3,}$")
    reviewer_persona: str = Field(strict=True)
    status: str = Field(strict=True)
    design_flaws: list[str] = Field(strict=True, max_length=2, default_factory=list)
    test_design_flaws: list[str] = Field(strict=True, max_length=2, default_factory=list)
    accepted_tradeoffs: list[str] = Field(strict=True, default_factory=list)
    reviewed_at: datetime = Field(strict=False)

    model_config = {"frozen": True}
