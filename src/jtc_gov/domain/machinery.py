import re
from typing import Final

_GLOBS: Final = (
    ".github/**",
    "scripts/**",
    "pyproject.toml",
    "uv.lock",
    ".pre-commit-config.yaml",
    ".gitattributes",
    ".claude/settings.json",
    ".claude/hooks/**",
    ".coveragerc",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "**/conftest.py",
    "AGENT.md",
    "CLAUDE.md",
    "src/jtc_gov/**",
)


def _to_regex(glob: str) -> re.Pattern[str]:
    out = ""
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            out += ".*"
            i += 2
        else:
            out += re.escape(glob[i])
            i += 1
    return re.compile(f"^{out}\\Z")


MACHINERY: Final = tuple((g, _to_regex(g)) for g in _GLOBS)


def machinery_reason(path: str) -> str | None:
    return next((name for name, pattern in MACHINERY if pattern.match(path)), None)
