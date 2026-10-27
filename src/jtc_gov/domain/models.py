import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from jtc_gov.domain.gates import APPROVED_FILE_PATTERN
from jtc_gov.domain.ids import RequirementId

Ref = Literal["base", "head"]
Status = Literal["added", "modified", "deleted", "renamed"]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


@dataclass(frozen=True)
class Change:
    old_path: str | None
    new_path: str | None
    status: Status

    def __post_init__(self) -> None:
        old, new = self.old_path is not None, self.new_path is not None
        valid = {
            "added": (not old) and new,
            "deleted": old and not new,
            "modified": old and new and self.old_path == self.new_path,
            "renamed": old and new and self.old_path != self.new_path,
        }[self.status]
        if not valid:
            msg = f"invalid change: {self}"
            raise ValueError(msg)

    def paths(self) -> tuple[str, ...]:
        return tuple(p for p in (self.old_path, self.new_path) if p is not None)


class ApprovalState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    WITHDRAWN = "withdrawn"


class Approval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    requirement: RequirementId
    state: ApprovalState = Field(strict=False)
    files: dict[str, Sha256]

    @field_validator("files")
    @classmethod
    def _keys(cls, files: dict[str, str]) -> dict[str, str]:
        bad = [k for k in files if not re.match(APPROVED_FILE_PATTERN, k)]
        if bad:
            msg = f"invalid file keys: {bad}"
            raise ValueError(msg)
        return files


@dataclass(frozen=True)
class ParseFailure:
    reason: str


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str | None
    message: str
    hint: str | None = None


@dataclass(frozen=True)
class CheckResult:
    findings: tuple[Finding, ...]
    human_merge: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.findings
