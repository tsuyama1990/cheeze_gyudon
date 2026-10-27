from jtc_gov.domain.gates import DELIVERABLES
from jtc_gov.domain.models import Ref
from jtc_gov.domain.repo import Repo

_COMPLETE_GATE = 5


def _present(repo: Repo, ref: Ref, req: str, name: str) -> bool:
    return bool(repo.read(f".specs/{req}/{name}", ref))


def display_gate(repo: Repo, ref: Ref, req: str) -> int:
    for deliverable in DELIVERABLES:
        if not (
            _present(repo, ref, req, deliverable.design)
            and _present(repo, ref, req, deliverable.test_spec)
        ):
            return deliverable.gate
    return _COMPLETE_GATE
