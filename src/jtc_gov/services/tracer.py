import ast
import re
from pathlib import Path

from jtc_gov.domain.exceptions import TraceabilityMismatchError
from jtc_gov.services.state_engine import read_state


def extract_requirements_from_spec(spec_path: Path) -> set[str]:
    """
    Extracts all requirements tagged as [REQ-xxx] or [REQ-xxx-Fyy] from a Markdown spec.
    """
    if not spec_path.exists():
        return set()

    content = spec_path.read_text(encoding="utf-8")
    # Matches tags like [REQ-2026-001] or [REQ-2026-001-F01]
    pattern = r"\[(REQ-\d{4}-\d{3,}(?:-F\d{2,})?)\]"
    matches = re.findall(pattern, content)
    return set(matches)


def extract_requirements_from_tests(tests_dir: Path) -> set[str]:
    """
    Parses Python test files in tests_dir using AST and extracts requirements
    from @pytest.mark.requirement("REQ-xxx") decorators.
    """
    if not tests_dir.exists() or not tests_dir.is_dir():
        return set()

    found_reqs: set[str] = set()

    for filepath in tests_dir.rglob("*.py"):
        try:
            content = filepath.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(filepath))
            _extract_reqs_from_tree(tree, found_reqs)
        except SyntaxError:
            continue

    return found_reqs


def _extract_reqs_from_tree(tree: ast.AST, found_reqs: set[str]) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                _process_decorator(decorator, found_reqs)


def _process_decorator(decorator: ast.expr, found_reqs: set[str]) -> None:
    if isinstance(decorator, ast.Call):
        func = decorator.func
        is_req_mark = False

        if (isinstance(func, ast.Attribute) and func.attr == "requirement") or (
            isinstance(func, ast.Name) and func.id == "requirement"
        ):
            is_req_mark = True

        if is_req_mark and decorator.args:
            arg = decorator.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found_reqs.add(arg.value)


def verify_traceability() -> None:
    """
    Verifies that all feature tags (REQ-xxx-Fnn) of the active requirement defined in its
    spec are covered by tests, and vice versa. Tags of other requirements are ignored.
    """
    state = read_state()
    active_id = state.active_requirement_id

    spec_dir = Path(f".specs/{active_id}")
    spec_path = spec_dir / "01_req_spec.md"
    tests_dir = Path("tests")

    if not spec_path.exists():
        msg = f"Spec file {spec_path} does not exist."
        raise TraceabilityMismatchError(msg)

    feature_tag = re.compile(rf"{re.escape(active_id)}-F\d{{2,}}")
    spec_reqs = {r for r in extract_requirements_from_spec(spec_path) if feature_tag.fullmatch(r)}
    test_reqs = {r for r in extract_requirements_from_tests(tests_dir) if feature_tag.fullmatch(r)}

    missing_in_tests = spec_reqs - test_reqs
    missing_in_spec = test_reqs - spec_reqs

    if missing_in_tests or missing_in_spec:
        error_msg = ["Bidirectional traceability mismatch detected:"]
        if missing_in_tests:
            error_msg.append(f"  Missing test coverage for: {', '.join(missing_in_tests)}")
        if missing_in_spec:
            error_msg.append(f"  Scope creep / undefined in spec: {', '.join(missing_in_spec)}")

        raise TraceabilityMismatchError("\n".join(error_msg))
