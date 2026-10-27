# jtc-gov

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/package_manager-uv-green.svg)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Mypy Strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy.readthedocs.io/)

A CLI and CI checks that keep AI-written changes in order: new behavior reaches `main` only after a human has approved the design.

**Status: design in progress.** Several parts of the target design are not enforced yet. Everything below is a pointer; the content lives in one place each.

| What | Where |
|---|---|
| Requirements, guarantees, non-guarantees | [.specs/REQ-2026-010/01_req_spec.md](.specs/REQ-2026-010/01_req_spec.md) |
| Design | [.specs/REQ-2026-010/02_system_design.md](.specs/REQ-2026-010/02_system_design.md) |
| Decisions | [.specs/REQ-2026-010/decisions.md](.specs/REQ-2026-010/decisions.md) |
| Progress and process | [.specs/REQ-2026-010/spirals.md](.specs/REQ-2026-010/spirals.md) |
| What is enforced today (measured) | [.specs/REQ-2026-010/background/as_is_inventory.md](.specs/REQ-2026-010/background/as_is_inventory.md) |
| Rules for AI agents | [AGENT.md](AGENT.md) |
| Original outline (historical) | [doc/jtc_governance_framework.md](doc/jtc_governance_framework.md) |

## Setup and checks

Requirements: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Git.

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
scripts/gate.sh        # the single entry point for the quality gate
uv run gov --help
uv run gov check       # K / D / T / Q.pragma against origin/main (exit 0 pass, 1 violation, 2 not evaluated)
uv run gov status      # approvals per requirement
```

## License

MIT. See [LICENSE](LICENSE).
