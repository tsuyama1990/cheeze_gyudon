# JTC-Style AI-Driven Development Governance Platform (`jtc-gov`)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/package_manager-uv-green.svg)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Mypy Strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy.readthedocs.io/)
[![Coverage](https://img.shields.io/badge/branch__coverage-%E2%89%A590%25-brightgreen.svg)]()

> **"Uncompromising Engineering Rigor Meets Autonomous AI Development"**
> An industrial-grade, zero-trust governance platform that mechanically halts AI agent runaway, specification drift, code bloat, and self-serving test generation using symmetric V-Model gates, multi-persona red teaming, and kernel-level tool interception.

---

## 1. Executive Summary & Problem Space

While autonomous AI coding agents (Claude Code, Jules, Copilot Workspace) accelerate code production by orders of magnitude, unconstrained agents systematically exhibit five universal software engineering distortions:

| AI Distortion | Failure Mode in Unconstrained AI | Mechanical Mitigation in `jtc-gov` |
| :--- | :--- | :--- |
| **1. Tautological Testing** | AI writes buggy code and writes matching buggy tests that test nothing, yielding green CI on invalid logic. | **Scaffold Lock**: Tests and scaffolds are defined upstream in Gates 1–4 before `src/` is unlocked. AI cannot alter test assertions during implementation. |
| **2. Patch-on-Patch Decay** | AI fixes bugs with superficial try/except wrappers and monkey-patches, causing cyclomatic complexity to explode. | **Complexity Ceiling**: Ruff McCabe limit (`complexity <= 10`), max 30 statements per function, zero tolerance for print debugging (`T201`). |
| **3. Works-on-My-Machine** | AI installs undeclared system libraries or relies on unpinned transitive versions. | **Hermetic Reproducibility**: Strict `uv.lock`, Pydantic Settings environment validation, and zero implicit globals. |
| **4. Zombie / Dead Code** | AI duplicates helpers instead of refactoring existing modules, accumulating bloat. | **Vulture Zero Tolerance**: Dead code detection with confidence $\ge 80\%$ fails the build immediately. |
| **5. Mock Drift** | Mocked interfaces silently drift from external API realities. | **Contract Scaffolding**: Schema-driven test fixtures generated directly from OpenAPI/JSON Schema. |

---

## 2. Core Architecture: The Symmetric V-Model Gates

Development is partitioned into 5 rigid V-Model counterpart gates. An agent **cannot write production code** (`src/`) until Gates 1 through 4 have passed multi-persona adversarial review and received formal sign-off.

```mermaid
flowchart TD
    subgraph Downstream_Design["Downstream Design (Upstream V)"]
        G1_D["Gate 1: Requirements Definition<br/><code>01_req_spec.md</code>"]
        G2_D["Gate 2: System Architecture<br/><code>02_system_design.md</code>"]
        G3_D["Gate 3: Integration Design<br/><code>03_architecture.md</code>"]
        G4_D["Gate 4: Detailed Class Design<br/><code>04_detail_design.md</code>"]
    end

    subgraph Decision["Gate 4.5: Tri-Polar Decision & Human Sign-off"]
        DEC["Tri-Polar Option Selection & Sign-off<br/><code>05_decision.md</code><br/>(KISS vs. Standard vs. Scalable)"]
    end

    subgraph Upstream_Verification["Upstream Verification (Counterpart V)"]
        G1_T["Acceptance Tests (BDD/Gherkin)<br/><code>01_acceptance_tests.feature</code>"]
        G2_T["System Test Scenarios<br/><code>02_system_tests.md</code>"]
        G3_T["Integration Contract Tests<br/><code>03_integration_tests.md</code>"]
        G4_T["Unit Test Scaffold Lock<br/><code>04_unit_test_scaffold/</code>"]
    end

    subgraph Implementation["Gate 5: Implementation & Verification"]
        G5_CODE["Code & Test Execution<br/><code>src/</code> + <code>tests/</code><br/>(Branch Coverage >= 90%)"]
    end

    G1_D <== Pair Enforced ==> G1_T
    G1_T --> G2_D
    G2_D <== Pair Enforced ==> G2_T
    G2_T --> G3_D
    G3_D <== Pair Enforced ==> G3_T
    G3_T --> G4_D
    G4_D <== Pair Enforced ==> G4_T
    G4_T --> DEC
    DEC --> G5_CODE
```

### Gate Deliverables Matrix

| Gate | Phase | Design Deliverable | Counterpart Test Deliverable | Required Review Personas |
| :--- | :--- | :--- | :--- | :--- |
| **Gate 1** | Requirements Definition | `.specs/REQ-xxx/01_req_spec.md` | `01_acceptance_tests.feature` | UX Critic, Lazy Senior Dev, FinOps/Sec |
| **Gate 2** | System Architecture | `.specs/REQ-xxx/02_system_design.md` | `02_system_tests.md` | System Architect, SRE Persona |
| **Gate 3** | Integration Design | `.specs/REQ-xxx/03_architecture.md` | `03_integration_tests.md` | Interface Architect, QA Lead |
| **Gate 4** | Detailed Class Design | `.specs/REQ-xxx/04_detail_design.md` | `04_unit_test_scaffold/` | Code Quality Critic, Security Persona |
| **Decision**| Tri-Polar Triage | `.specs/REQ-xxx/05_decision.md` | Multi-Option Trade-off Analysis | **Human Sign-Off / Negative Consensus** |

> `gov gate-check --gate 4` refuses to advance unless `05_decision.md` contains the line `HUMAN_SIGN_OFF: APPROVED`. **Known gap:** `gov draft-decision` currently writes that line itself, so the sign-off is not yet human-only. See [doc/as_is_inventory.md](doc/as_is_inventory.md) (defect A) and [doc/open_design_decisions.md](doc/open_design_decisions.md) (D3).
| **Gate 5** | Coding & Verification | `src/` (Implementation) | `tests/` (`@pytest.mark.requirement`) | Automated CI, Branch Coverage $\ge 90\%$ |

---

## 3. Four-Layer Enforcement Taxonomy

Governance rules are physically enforced across four runtime boundaries to guarantee zero-trust execution:

```mermaid
flowchart LR
    L1["Layer 1: Protocol<br/>(state.json & Schemas)"] --> L2["Layer 2: Review<br/>(Adversarial Personas)"]
    L2 --> L3["Layer 3: Real-time Control<br/>(PreToolUse Hooks)"]
    L3 --> L4["Layer 4: Local Git Gates<br/>(pre-commit & pre-push)"]
    L4 --> L5["Layer 5: Remote CI/CD<br/>(Air-gapped GitHub Actions)"]
```

1. **Layer 1: Protocol & State Machine (`.specs/state.json`)**:
   Tracks the active requirement ID, current gate, and explicit whitelist of editable paths (`unlocked_paths`).
2. **Layer 2: Adversarial Red Teaming & Decision Protocol**:
   Automated single-turn review personas that produce strictly validated `gate_review.json` deliverables (max 2 fatal flaws).
3. **Layer 3: Agent Kernel Interception (`.agent/settings.json` / `PreToolUse`)**:
   Intercepts file editing tool calls (`Edit`, `Write`) in real-time. If the agent attempts to modify `src/` while `state.json` is at Gate 1–4, the tool call is rejected before execution.
4. **Layer 4: Local Git Enforcement (`pre-commit` & `pre-push`)**:
   - `pre-commit`: Blocks direct commits to `main`/`master`, executes Ruff (ALL rules), strict Mypy, Vulture, and duplicate code checks.
   - `pre-push`: Runs Pytest with $\ge 90\%$ branch coverage and enforces the **Documentation Sync Guard** (rejects `src/` diffs lacking documentation updates).
5. **Layer 5: Remote CI/CD**:
   Air-gapped, zero-credential-leakage GitHub Actions running `gov ci-verify` (bidirectional traceability of the active requirement's `REQ-xxx-Fnn` tags) and `scripts/verify_all.sh` (lint, types, dead/duplicate code, tests with coverage, pre-commit).

---

## 4. Repository Layout & Dogfooding Architecture

This repository strictly dogfoods the `jtc-gov` framework:

```text
cheeze_gyudon/
├── .agent/
│   └── settings.json                  # Real-time PreToolUse tool interception hook
├── .specs/
│   ├── state.json                     # Finite State Machine tracking active gate
│   └── REQ-2026-001/                  # Active requirement: jtc-gov Phase 1 CLI
│       ├── 01_req_spec.md             # Gate 1 Requirements & 3-pole options
│       └── 01_acceptance_tests.feature# Gate 1 BDD Acceptance test scenarios
├── doc/
│   └── jtc_governance_framework.md    # Canonical specification document (710 lines)
├── src/
│   └── jtc_gov/                       # Production governance CLI package
│       ├── __init__.py                # Package metadata
│       └── cli.py                     # Click CLI entrypoint skeleton
├── tests/
│   └── test_version.py                # Initial unit test linked to REQ-INIT-001
├── .pre-commit-config.yaml            # Ultra-strict local pre-commit & pre-push hooks
├── pyproject.toml                     # Modern uv/hatchling project configuration
├── AGENT.md                           # Universal agent constitution & guardrails
├── CLAUDE.md                          # Claude Code adapter instructions
└── README.md                          # This document
```

---

## 5. Reverse Escalation Protocol (`gov escalate`)

When an AI agent is in Gate 5 (Implementation) and discovers an insurmountable upstream specification flaw or dependency block:
1. The agent is **strictly prohibited** from patching around the problem with local hacks.
2. The agent executes `gov escalate --gate <target_gate> --reason "<detailed explanation>"`.
3. The state machine rolls back `state.json` to the target gate (e.g. `GATE1_SPEC`), immediately **re-locking** `src/` and unlocking the upstream specification file.
4. The specification and test counterpart are corrected, re-reviewed, and re-approved before `src/` can be edited again.

---

## 6. Quickstart & Local Development

### Prerequisites
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (Astral Python package manager)
- Git

### Setup

```bash
# 1. Clone repository
git clone https://github.com/tsuyama1990/cheeze_gyudon.git
cd cheeze_gyudon

# 2. Sync dependencies hermetically using uv
uv sync

# 3. Install pre-commit and pre-push constitution hooks
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

### Running Checks

```bash
# Run Ruff linting and formatting
uv run ruff check --fix
uv run ruff format

# Run ultra-strict Mypy type verification
uv run mypy src tests

# Run dead code eradication check
uv run vulture src --min-confidence 80

# Run one-stop governance verification suite (Ruff, Mypy, Vulture, Duplicates, Pytest, Hooks)
bash scripts/verify_all.sh

# Run duplicate code detection
uv run python scripts/check_duplicates.py

# Test the governance CLI status and tool verification
# (`gov init` in a new project scaffolds requirement REQ-0000-001; rename it to your own REQ-YYYY-NNN)
uv run gov status
uv run gov verify-tool --file README.md
```

---

## 7. Roadmap & Next Steps

- [x] **Phase 0: Canonical Specification & Dogfooding Setup**
  - Exhaustive architecture document (`doc/jtc_governance_framework.md`)
  - Ultra-strict pre-commit and pre-push guardrails
  - Initial dogfooding state structure (`.specs/state.json`)
- [ ] **Phase 1: Core CLI & State Engine Implementation (Jules Handover)**
  - `gov init`: Scaffold `.specs/` and hook configurations
  - `gov verify-tool`: Low-latency (<50ms) tool interception engine
  - `gov gate-check`: Deliverable & schema validator across Gates 1–5
  - `gov trace-check`: AST-based bidirectional requirement traceability
  - `gov escalate`: Structured upstream rollback protocol
  - `gov audit-push`: Air-gapped push validation
- [ ] **Phase 2: Adversarial Persona Templates & Subagent Review Engine**
- [ ] **Phase 3: GitHub Actions & Air-Gapped Remote CI Integration**
- [ ] **Phase 4: Full Multi-Agent Pilot Operations**

---

## 8. License

This project is licensed under the MIT License - see the LICENSE file for details.
Phase 3 updates for PR formatting and summary generation completed.
