import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src" / "jtc_gov"
DETAIL_DESIGN = Path(__file__).parents[2] / ".specs" / "REQ-2026-010" / "04_detail_design.md"
LAYERS = ("domain", "derive", "checks", "adapters")
PURE_LAYERS = LAYERS[:3]
IO_MODULES = {
    "subprocess",
    "os",
    "pathlib",
    "shutil",
    "tempfile",
    "socket",
    "urllib",
    "time",
    "datetime",
    "random",
}


def modules(layers: tuple[str, ...] = LAYERS) -> list[Path]:
    return sorted(p for layer in layers for p in (SRC / layer).glob("*.py"))


def imported(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.parametrize("path", modules(PURE_LAYERS), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_pure_layers_do_not_do_io(path: Path) -> None:
    """L1-S01"""
    roots = {n.split(".")[0] for n in imported(path)}
    assert not roots & IO_MODULES
    calls = {
        n.func.id
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert not calls & {"open", "input", "print"}


@pytest.mark.requirement("REQ-2026-010-F01")
@pytest.mark.parametrize("path", modules(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_imports_point_down_only(path: Path) -> None:
    """L1-S02"""
    own = LAYERS.index(path.parent.name)
    for name in imported(path):
        parts = name.split(".")
        if parts[0] == "jtc_gov" and len(parts) > 1 and parts[1] in LAYERS:
            assert LAYERS.index(parts[1]) <= own, f"{path.name} imports {name}"


@pytest.mark.requirement("REQ-2026-010-F08")
@pytest.mark.parametrize(
    "path",
    [p for p in modules() if p.read_text(encoding="utf-8").strip()],
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_every_module_is_in_the_detail_design(path: Path) -> None:
    """L1-S03: the reverse direction (designed but missing) is checked when its adapter lands."""
    headings = set(
        re.findall(
            r"^### [\d.a-z]+ `([a-z_/]+\.py)`",
            DETAIL_DESIGN.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    assert f"{path.parent.name}/{path.name}" in headings


@pytest.mark.requirement("REQ-2026-010-F06")
def test_nothing_writes_state_json() -> None:
    """L1-S04"""
    offenders = [p.name for p in SRC.rglob("*.py") if "state.json" in p.read_text(encoding="utf-8")]
    assert offenders == []
