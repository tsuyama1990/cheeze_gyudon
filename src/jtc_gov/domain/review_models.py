"""Domain models for Gate Reviews."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_FLAWS = 2


class GateReview(BaseModel):
    """Immutable model representing a gate review."""

    model_config = ConfigDict(frozen=True)

    gate_id: str
    requirement_id: str
    reviewer_persona: str
    status: Literal["APPROVED", "REJECTED"]
    design_flaws: list[str] = Field(default_factory=list)
    test_design_flaws: list[str] = Field(default_factory=list)
    accepted_tradeoffs: list[str] = Field(default_factory=list)
    reviewed_at: str

    @model_validator(mode="after")
    def validate_max_flaws(self: Self) -> Self:
        """Validate that max items in flaws lists does not exceed 2."""
        if len(self.design_flaws) > MAX_FLAWS:
            msg = "design_flaws cannot have more than 2 items."
            raise ValueError(msg)
        if len(self.test_design_flaws) > MAX_FLAWS:
            msg = "test_design_flaws cannot have more than 2 items."
            raise ValueError(msg)
        return self
