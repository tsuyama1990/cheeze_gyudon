# [REQ-2026-001] JTC-Style Governance Framework CLI Core Engine

## 1. Background & Scope
This specification defines the core engine for `jtc-gov`, a Python-based CLI and hook suite that mechanically prevents AI coding runaway across the V-Model.

## 2. Requirements & Capabilities
- **[REQ-2026-001-F01] State Machine Enforcement**: Maintain and validate `.specs/state.json`. Block file editing outside `unlocked_paths`.
- **[REQ-2026-001-F02] Paired Deliverable Verification (`gov gate-check`)**: Ensure design and test counterparts exist and reviews are APPROVED.
- **[REQ-2026-001-F03] Bidirectional AST Traceability (`gov trace-check`)**: Verify 100% mutual correspondence between `[REQ-xxx]` tags and `@pytest.mark.requirement`.
- **[REQ-2026-001-F04] Real-time PreToolUse Interception (`gov verify-tool`)**: Execute in < 50ms, aborting unauthorized file writes.
- **[REQ-2026-001-F05] Reverse Escalation (`gov escalate`)**: Re-lock `src/` and roll back state upon downstream blockers.

## 3. Mandatory 3-Pole Option Evaluation
- **Option A (KISS Pole)**: Plain Python standard library CLI (`argparse`, manual JSON schema checks). Zero external dependencies.
- **Option B (Industry Standard Pole - SELECTED)**: `click` + `pydantic v2` + `jsonschema`. Typed models and schema validation.
- **Option C (Radical Scalable Pole)**: Event-driven async plugin architecture. High complexity, deferred to future enterprise federations.
