# AI Agent Governance & Behavioral Constitution

You are operating within a repository governed by the **JTC-Style Governance Framework**.
Your behavior is constrained by physical execution hooks, state machines, and quality ceilings.

## 1. Prime Directive: Zero Code Without Unlocked Gates
- You MUST NOT attempt to edit or create production code under `src/` until `.specs/state.json` reaches `GATE4_DETAIL` completion and contains explicit human sign-off in `05_decision.md`.
- Attempting to modify `src/` out of phase will be physically intercepted and terminated by `gov verify-tool` with exit code 1.

## 2. Shift-Left Test Design Symmetry
- Every design document MUST have a simultaneously created counterpart test specification:
  - Gate 1: `01_req_spec.md` + `01_acceptance_tests.feature` (BDD/Gherkin)
  - Gate 2: `02_system_design.md` + `02_system_tests.md` (Failure matrix)
  - Gate 3: `03_architecture.md` + `03_integration_tests.md` (Pydantic models & boundary contracts)
  - Gate 4: `04_detail_design.md` + `tests/test_*.py` (Frozen scaffolds with `@pytest.mark.requirement`)

## 3. Anti-Distortion & Quality Rules
1. **Never Re-invent the Wheel**: Conduct PyPI/OSS survey before writing custom utilities.
2. **Never Weaken Test Assertions**: Altering frozen test expectations during Gate 5 to pass broken code is strictly prohibited.
3. **No Magic Constants / Hardcoding**: All configuration must be externalized into typed Pydantic settings.
4. **Clean Architecture Lite**: Strict inward dependencies (`adapters` -> `services` -> `domain`).
5. **Ultra-Strict Code Quality**:
   - Cyclomatic Complexity <= 10 (`ruff`).
   - Branch Coverage >= 90% (`pytest --cov-branch`).
   - Zero duplicate code (`jscpd`).
   - Zero dead code (`vulture`).
