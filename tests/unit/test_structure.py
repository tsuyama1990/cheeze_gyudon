import ast
from pathlib import Path

import pytest

from tests.support.specs import CLOSED, designed_modules

SRC = Path(__file__).parents[2] / "src" / "jtc_gov"
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
    assert f"{path.parent.name}/{path.name}" in designed_modules()


@pytest.mark.requirement("REQ-2026-010-F06")
def test_nothing_writes_state_json() -> None:
    """L1-S04"""
    offenders = [p.name for p in SRC.rglob("*.py") if "state.json" in p.read_text(encoding="utf-8")]
    assert offenders == []


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(SRC.parent).with_suffix("").parts)


@pytest.mark.requirement("REQ-2026-010-F08")
@pytest.mark.spec("L1-S02")
def test_module_imports_have_no_cycles() -> None:
    graph = {
        _module_name(p): {n for n in imported(p) if n.startswith("jtc_gov.")}
        for p in SRC.rglob("*.py")
    }
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str) -> None:
        assert node not in visiting, f"import cycle through {node}"
        if node in done or node not in graph:
            return
        visiting.add(node)
        for target in graph[node]:
            visit(target)
        visiting.discard(node)
        done.add(node)

    for name in graph:
        visit(name)


@pytest.mark.requirement("REQ-2026-010-F08")
@pytest.mark.spec("L1-S03")
def test_every_designed_module_exists() -> None:
    """Only closed requirements: an open one is still adding its modules."""
    missing = sorted(h for h in designed_modules({CLOSED}) if not (SRC / h).is_file())
    assert missing == []
