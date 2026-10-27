from collections.abc import Mapping, Sequence

from jtc_gov.domain.models import Change, Ref


class FakeRepo:
    def __init__(
        self,
        base: Mapping[str, bytes],
        head: Mapping[str, bytes],
        renames: Mapping[str, str] | None = None,
    ) -> None:
        self._files = {"base": dict(base), "head": dict(head)}
        self._renames = dict(renames or {})

    def read(self, path: str, ref: Ref) -> bytes | None:
        return self._files[ref].get(path)

    def list(self, ref: Ref) -> Sequence[str]:
        return sorted(self._files[ref])

    def changes(self) -> Sequence[Change]:
        base, head = self._files["base"], self._files["head"]
        moved_to = set(self._renames.values())
        out = [Change(old, new, "renamed") for old, new in self._renames.items()]
        for path in sorted(base.keys() - self._renames.keys()):
            if path not in head:
                out.append(Change(path, None, "deleted"))
            elif base[path] != head[path]:
                out.append(Change(path, path, "modified"))
        out += [Change(None, p, "added") for p in sorted(head.keys() - base.keys() - moved_to)]
        return out


def approval_json(req: str, state: str, files: dict[str, bytes]) -> bytes:
    import hashlib
    import json

    digests = {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}
    return json.dumps({"requirement": req, "state": state, "files": digests}).encode()


def design_files(req: str, spec: str = "- **[REQ-2026-010-F01] x**\n") -> dict[str, bytes]:
    names = [
        "01_req_spec.md",
        "01_acceptance_tests.feature",
        "02_system_design.md",
        "02_system_tests.md",
        "03_architecture.md",
        "03_integration_tests.md",
        "04_detail_design.md",
        "04_unit_tests.md",
    ]
    return {f".specs/{req}/{n}": (spec if n == "01_req_spec.md" else n).encode() for n in names}


def with_approval(
    req: str, state: str = "open", spec: str = "- **[REQ-2026-010-F01] x**\n"
) -> dict[str, bytes]:
    files = design_files(req, spec)
    guarded = {p.rsplit("/", 1)[1]: b for p, b in files.items()}
    return {**files, f".specs/{req}/approval.json": approval_json(req, state, guarded)}
