import pytest
from pydantic import ValidationError

from jtc_gov.domain.gates import APPROVED_FILE_PATTERN, DELIVERABLES, GUARDED_PREFIX
from jtc_gov.domain.ids import requirement_of
from jtc_gov.domain.machinery import machinery_reason
from jtc_gov.domain.models import Approval, Change, CheckResult, Finding

SHA = "a" * 64


@pytest.mark.requirement("REQ-2026-010-F03")
@pytest.mark.parametrize(
    ("tag", "req"),
    [("REQ-2026-010-F01", "REQ-2026-010"), ("REQ-2026-010-F99", "REQ-2026-010")],
)
def test_requirement_of_valid(tag: str, req: str) -> None:
    assert requirement_of(tag) == req


@pytest.mark.requirement("REQ-2026-010-F03")
@pytest.mark.parametrize("tag", ["REQ-2026-010", "req-2026-010-f01", "REQ-INIT-001"])
def test_requirement_of_invalid(tag: str) -> None:
    with pytest.raises(ValueError, match="not a feature tag"):
        requirement_of(tag)


@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.parametrize(
    ("old", "new", "status"),
    [
        ("a", "b", "added"),
        (None, None, "added"),
        ("a", "b", "deleted"),
        ("a", None, "renamed"),
        ("a", "b", "modified"),
        ("a", "a", "renamed"),
    ],
)
def test_change_invariants_invalid(old: str | None, new: str | None, status: str) -> None:
    with pytest.raises(ValueError, match="invalid change"):
        Change(old, new, status)  # type: ignore[arg-type]


@pytest.mark.requirement("REQ-2026-010-F01")
def test_change_paths() -> None:
    assert Change(None, "n", "added").paths() == ("n",)
    assert Change("o", None, "deleted").paths() == ("o",)
    assert Change("p", "p", "modified").paths() == ("p", "p")
    assert Change("o", "n", "renamed").paths() == ("o", "n")


def _approval(**over: object) -> dict[str, object]:
    return {
        "requirement": "REQ-2026-010",
        "state": "open",
        "files": {"01_req_spec.md": SHA},
        **over,
    }


@pytest.mark.requirement("REQ-2026-010-F02")
def test_approval_valid() -> None:
    assert Approval.model_validate(_approval()).state.value == "open"


@pytest.mark.requirement("REQ-2026-010-F02")
@pytest.mark.parametrize(
    "bad",
    [
        _approval(state="done"),
        _approval(files={"sub/01_req_spec.md": SHA}),
        _approval(files={"06_x.md": SHA}),
        _approval(files={"01_req_spec.md": "A" * 64}),
        _approval(files={"01_req_spec.md": "a" * 63}),
        _approval(extra=1),
        _approval(requirement="REQ-INIT"),
    ],
)
def test_approval_invalid(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Approval.model_validate(bad)


@pytest.mark.requirement("REQ-2026-010-F01")
def test_check_result_ok() -> None:
    assert CheckResult((), ()).ok
    assert not CheckResult((Finding("K.a", None, "m"),), ()).ok


@pytest.mark.requirement("REQ-2026-010-F02")
def test_gate_patterns() -> None:
    assert [d.gate for d in DELIVERABLES] == [1, 2, 3, 4]
    for name in ("01_req_spec.md", "05_decision.md"):
        assert APPROVED_FILE_PATTERN.match(name)
    for name in ("06_x.md", "notes.md", "01_notes/extra.md"):
        assert not APPROVED_FILE_PATTERN.match(name)
    assert GUARDED_PREFIX.match("01_notes/extra.md")
    assert not GUARDED_PREFIX.match("notes.md")


@pytest.mark.requirement("REQ-2026-010-F07")
@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/x.yml",
        "scripts/gate.sh",
        "pyproject.toml",
        "uv.lock",
        ".pre-commit-config.yaml",
        ".gitattributes",
        ".claude/settings.json",
        ".claude/hooks/a.sh",
        "conftest.py",
        "tests/sub/conftest.py",
        "AGENT.md",
        "CLAUDE.md",
        "src/jtc_gov/adapters/cli.py",
    ],
)
def test_machinery_hits(path: str) -> None:
    assert machinery_reason(path)


@pytest.mark.requirement("REQ-2026-010-F07")
@pytest.mark.parametrize(
    "path", ["src/other/x.py", "docs/x.md", ".specs/REQ-2026-010/approval.json", "xconftest.py"]
)
def test_machinery_misses(path: str) -> None:
    assert machinery_reason(path) is None
