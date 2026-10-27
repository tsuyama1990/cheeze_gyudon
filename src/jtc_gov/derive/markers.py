import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass

from jtc_gov.derive.hashing import sha256_hex
from jtc_gov.domain.models import ParseFailure

_MARKER = "requirement"
_COMPOUND = (ast.If, ast.Try, ast.TryStar, ast.With, ast.For, ast.While, ast.Match)
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class TestFunction:
    __test__ = False

    qualname: str
    tags: tuple[str, ...]
    has_marker: bool
    source_sha: str
    lineno: int


@dataclass(frozen=True)
class _Marks:
    tags: tuple[str, ...] = ()
    has_marker: bool = False

    def plus(self, other: "_Marks") -> "_Marks":
        return _Marks(self.tags + other.tags, self.has_marker or other.has_marker)


def _marks(exprs: Iterable[ast.expr]) -> _Marks:
    tags: list[str] = []
    found = False
    for expr in exprs:
        if not isinstance(expr, ast.Call):
            continue
        func = expr.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name != _MARKER:
            continue
        found = True
        first = expr.args[0] if expr.args else None
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            tags.append(first.value)
    return _Marks(tuple(tags), found)


def _blocks(stmt: ast.stmt) -> list[list[ast.stmt]]:
    if isinstance(stmt, ast.Try | ast.TryStar):
        return [stmt.body, *(h.body for h in stmt.handlers), stmt.orelse, stmt.finalbody]
    if isinstance(stmt, ast.Match):
        return [case.body for case in stmt.cases]
    return [getattr(stmt, "body", []), getattr(stmt, "orelse", [])]


def _flatten(stmts: Iterable[ast.stmt]) -> Iterable[ast.stmt]:
    for stmt in stmts:
        if isinstance(stmt, _COMPOUND):
            for block in _blocks(stmt):
                yield from _flatten(block)
        else:
            yield stmt


def _module_marks(stmts: Iterable[ast.stmt]) -> _Marks:
    marks = _Marks()
    for stmt in stmts:
        if isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets
        ):
            value = stmt.value
            items = value.elts if isinstance(value, ast.List | ast.Tuple) else [value]
            marks = _marks(items)
    return marks


def test_functions(source: bytes) -> list[TestFunction] | ParseFailure:
    try:
        tree = ast.parse(source)
        lines = re.split(r"\r\n|\r|\n", source.decode("utf-8"))
    except (SyntaxError, ValueError) as e:
        return ParseFailure(str(e))
    top = list(_flatten(tree.body))
    module = _module_marks(top)
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, _Marks]] = []
    for stmt in top:
        if isinstance(stmt, _FUNCTIONS) and stmt.name.startswith("test_"):
            found.append((stmt.name, stmt, module))
        elif isinstance(stmt, ast.ClassDef) and stmt.name.startswith("Test"):
            cls = module.plus(_marks(stmt.decorator_list))
            found += [
                (f"{stmt.name}.{m.name}", m, cls)
                for m in stmt.body
                if isinstance(m, _FUNCTIONS) and m.name.startswith("test_")
            ]
    seen: dict[str, int] = {}
    result: list[TestFunction] = []
    for qualname, node, inherited in found:
        seen[qualname] = seen.get(qualname, 0) + 1
        name = qualname if seen[qualname] == 1 else f"{qualname}#{seen[qualname]}"
        marks = inherited.plus(_marks(node.decorator_list))
        first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        end = node.end_lineno or node.lineno
        text = "\n".join(lines[first - 1 : end])
        result.append(
            TestFunction(name, marks.tags, marks.has_marker, sha256_hex(text.encode()), node.lineno)
        )
    return result
