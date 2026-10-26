# Rules for AI agents

This repository follows the gate process described in `README.md`. Follow these rules yourself. The tooling does not stop you today: the PreToolUse hook is not active (`doc/as_is_inventory.md`, Section 5.1).

## 1. Do not edit `src/` before the gates are open
- Do not edit or create files under `src/` until `.specs/state.json` shows `GATE5_IMPL`. That happens after Gate 4 passes, which requires human sign-off in `05_decision.md`.

## 2. Write the test specification together with each design document
- Gate 1: `01_req_spec.md` and `01_acceptance_tests.feature` (Gherkin)
- Gate 2: `02_system_design.md` and `02_system_tests.md` (failure matrix)
- Gate 3: `03_architecture.md` and `03_integration_tests.md` (Pydantic models and boundary contracts)
- Gate 4: `04_detail_design.md` and `tests/test_*.py` (tests marked with `@pytest.mark.requirement`)

## 3. Quality rules
1. **Search before writing.** Check PyPI and existing OSS before writing a custom utility.
2. **Do not weaken tests.** Do not change test expectations in Gate 5 to make failing code pass.
3. **No hard-coded values.** Put configuration in typed Pydantic settings.
4. **Dependency direction:** `adapters` -> `services` -> `domain`.
5. **Code quality limits:**
   - Cyclomatic complexity of 10 or less (`ruff`).
   - Branch coverage of 90% or more (`pytest --cov-branch`).
   - No duplicate code (`scripts/check_duplicates.py`).
   - No dead code (`vulture`).
