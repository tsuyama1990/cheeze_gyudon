import re
from typing import Annotated, Final

from pydantic import StringConstraints

REQUIREMENT_ID: Final = re.compile(r"^REQ-\d{4}-\d{3,}$")
FEATURE_TAG: Final = re.compile(r"^REQ-\d{4}-\d{3,}-F\d{2,}\Z")
RequirementId = Annotated[str, StringConstraints(pattern=REQUIREMENT_ID.pattern)]


def requirement_of(tag: str) -> str:
    if not FEATURE_TAG.match(tag):
        msg = f"not a feature tag: {tag!r}"
        raise ValueError(msg)
    return tag.rsplit("-F", 1)[0]
