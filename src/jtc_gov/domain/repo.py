from collections.abc import Sequence
from typing import Protocol

from jtc_gov.domain.models import Change, Ref


class Repo(Protocol):
    def read(self, path: str, ref: Ref) -> bytes | None: ...

    def list(self, ref: Ref) -> Sequence[str]: ...

    def changes(self) -> Sequence[Change]: ...
