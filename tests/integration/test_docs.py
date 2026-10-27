import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from jtc_gov.adapters.cli import render_gitattributes
from tests.integration.test_repo_git import git, root  # noqa: F401

PROJECT = Path(__file__).parents[2]
SPECS = PROJECT / ".specs" / "REQ-2026-010"
LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
EXTERNAL = ("http://", "https://", "mailto:")
NORMATIVE = (
    PROJECT / "AGENT.md",
    PROJECT / "README.md",
    SPECS / "01_req_spec.md",
    SPECS / "02_system_design.md",
)


def documents() -> list[Path]:
    return [PROJECT / "README.md", PROJECT / "AGENT.md", *sorted(SPECS.rglob("*.md"))]


@pytest.mark.requirement("REQ-2026-010-F08")
@pytest.mark.parametrize("doc", documents(), ids=lambda p: str(p.relative_to(PROJECT)))
def test_relative_links_point_at_existing_files(doc: Path) -> None:
    """L1-C07"""
    text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.DOTALL)
    targets = [t for t in LINK.findall(text) if not t.startswith(EXTERNAL)]
    missing = [t for t in targets if not (doc.parent / t).exists()]
    assert missing == []


@pytest.mark.requirement("REQ-2026-010-F08")
@pytest.mark.parametrize("doc", NORMATIVE, ids=lambda p: p.name)
def test_normative_documents_do_not_copy_the_coverage_threshold(doc: Path) -> None:
    """L1-C07: the threshold lives in pyproject.toml only."""
    config = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))
    threshold = config["tool"]["coverage"]["report"]["fail_under"]
    assert not re.search(rf"\b{threshold}\s*%", doc.read_text(encoding="utf-8"))


@pytest.mark.requirement("REQ-2026-010-F01")
def test_gitattributes_normalises_specs_to_lf(root: Path) -> None:  # noqa: F811
    """L2-I45, L2-I46: raw bytes are hashed, so CRLF must not survive a checkout."""
    (root / ".gitattributes").write_text(render_gitattributes())
    spec = root / ".specs" / "R" / "01_req_spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_bytes(b"line one\r\nline two\r\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "crlf")
    clone = root.parent / "clone"
    subprocess.run(["git", "clone", "-q", str(root), str(clone)], check=True)  # noqa: S603, S607
    assert (clone / ".specs" / "R" / "01_req_spec.md").read_bytes() == b"line one\nline two\n"
