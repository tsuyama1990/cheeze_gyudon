# AI-Driven Development Governance Platform (JTC-Style Governance Framework)

> **履歴文書(読み取り専用)。** 規範は [.specs/REQ-2026-010/](../.specs/REQ-2026-010/) にある。この文書の内容は、REQ-2026-010 に引き継がれたものと、MVP 外として見送ったもの(Review / red team、scaffold、Phase 5、`sandbox/` など。範囲は `01_req_spec.md` §2)に分かれる。食い違う場合は REQ-2026-010 が正しい。この文書は更新しない(更新すると二重管理になる)。

## Requirements Definition Outline & Basic Design Document

---

## 1. Background and Objectives

While software development leveraging generative AI (such as Claude Code) dramatically improves development speed, it introduces the following critical challenges:

- **Uncontrolled Code Bloat / YAGNI Violations**: Neglecting the reuse of existing code and automatically generating unnecessary helpers, excessive abstractions, and unrequested fallbacks.
- **Spec Drift (Specification vs. Implementation Drift)**: Loss of consistency between requirements definition (upper V-model) and implementation/testing (lower V-model), leading to AI writing and passing circular, invalid tests.
- **Blurred Boundaries of Responsibility**: "Evaporation of responsibility" caused by delegating final decisions to AI, alongside the hollowing out of prompt instructions ("wishful instructions").

This platform integrates the symmetry of the **V-Model** (simultaneous formulation of design and corresponding test design), GitHub Next's **Spec-Driven Development** philosophy, the **JTC (Multi-angle Review & Ringi Approval)** model, and hooks from the **Python ecosystem**. It provides a development pipeline that blocks unintended AI changes at each transition of the V-model.

---

## 2. Requirements Definition Outline

### 2.1 Business & Process Requirements

#### Strict Phase Separation with V-Model Counterpart Structure (Shift-Left Test Design)
Rather than separating the development lifecycle into a "design side (left-downward V)" and an "implementation/verification side (right-upward V)", each upstream design phase must formulate its corresponding test design as a mandatory pair:

1. **Requirements Definition & Acceptance Test Design**
2. **Basic / System Design & System Test Design**
3. **Functional / Architecture Design & Integration Test Design**
4. **Detailed / Class Design & Unit Test Scaffold Design**
5. **Coding / Test Implementation & Mechanical Verification (Implementation & Verification)**

Unless the completed deliverables of the preceding phase (design document + corresponding test specification/scaffold code), verification results at each gate, and approval flags are all present, transition to the next phase (unlocking file editing permissions and branch promotion) is blocked.

#### Multi-Angle Red Teaming & Single-Turn Review with PM-AI Triage
To prevent bureaucratic infinite-review deadlock while maintaining adversarial rigor, reviews operate under a **Single-Turn Triage Model**:
- **Pluggable & Context-Aware Personas**: Gate 1 personas are not fixed; they adapt to project scale via configuration (`config.yaml`):
  - *Solo / Small Tool Preset (2-3 personas)*: UX Critic (Needs/Simplicity), Lazy Senior Dev (OSS/KISS), FinOps/Sec Lite (API cost & license sanity).
  - *Startup / SaaS Preset (3 personas)*: CPO (MVP Scope), Tech Lead (Coupling/Feasibility), SRE/Sec (Resilience/Auth).
  - *Enterprise / JTC Preset (4 personas)*: Legal (IP/Terms), Finance (ROI/Budget), CPO (Strategy), COO (SLA/Ops).
  - *Dynamic AI Recommendation*: PM-AI can dynamically assign personas based on feature tags (e.g. adding Legal for payment modules).
- **Single-Turn Review Rule**: Each persona conducts **exactly one review turn**, limited to at most **2 Fatal Flaws** outputting structured JSON logs.
- **Autonomous Research-First Ambiguity Resolution**:
  - When encountering ambiguities or open questions in Gate 1, the AI agent must **first conduct self-directed investigation** via Web search and codebase exploration rather than stalling development with immediate human inquiries.
  - The AI records reasoned assumptions in `01_req_spec.md`. Direct human inquiries are reserved solely for unresolvable business-critical branch points.
- **Two-Stage Formulation (Direction Decision Before Test Generation)**:
  - To prevent wasted token generation and rework if high-level requirements shift, Gate 1 follows a 2-stage internal pipeline:
    1. *Stage 1 (Requirements & 3-Pole Options)*: PM-AI formulates `01_req_spec.md` with 3-pole options (KISS vs Standard vs Scalable) and executes single-turn persona reviews to lock in architectural direction.
    2. *Stage 2 (Counterpart Acceptance Formulation)*: Once the direction is triaged, PM-AI generates the concrete `01_acceptance_tests.feature` (BDD/Gherkin) in a single, accurate pass.
- **Negative-Consensus Auto-Progression**:
  - Upon successful verification of deliverables via `gov gate-check --gate 1`, the pipeline **automatically advances to Gate 2**.
  - PM-AI renders an asynchronous concise summary (Selected Option + 3-line Gherkin digest) to the developer/PR interface. Human intervention is asynchronous: work proceeds unimpeded unless the developer explicitly intervenes.

#### Gate 2: Basic System Design, Ecosystem Survey & System Test Formulation
Gate 2 bridges business requirements to system architecture while preventing the "Re-inventing the Wheel" anti-pattern:
- **Mandatory Ecosystem Survey (Anti-Wheel-Reinvention Discipline)**:
  - Before writing any architectural specification, PM-AI must conduct a mandatory survey of existing external resources (battle-tested PyPI packages, standard cloud/SaaS APIs, and existing internal modules).
  - *Core Ethos*: "The best code is no code at all." Writing hundreds of lines of custom code when a standard, well-maintained library exists is treated as a critical architectural defect.
  - `02_system_design.md` must explicitly document why external alternatives were selected or rejected.
- **Pre-definition of Configuration Schema (`config.yaml`)**:
  - Hardcoded magic numbers, default URLs, and timeouts are prohibited. All operational variables must be formally declared in `02_system_design.md` with explicit configuration schemas before implementation.
- **Mock Contract & Mandatory Failure Matrix (`02_system_tests.md`)**:
  - All external integrations must declare their mocking contract (e.g. `pytest-mock`, `respx`) upfront to prevent circular, invalid test suites.
  - Must include a **Mandatory Failure Matrix** covering 4 standard edge scenarios: ① Timeouts, ② Authentication errors, ③ Malformed payload validation, and ④ Upstream service unavailability.
- **Gate 2 Red Teaming Personas**:
  - Evaluated by **Tech Lead / Architect** (Loose coupling, KISS, reuse of existing assets) and **SRE / Security** (Threat modeling, auth boundaries, resilience).

#### Gate 3: Functional Architecture Design, Component Decomposition & Integration Tests
Gate 3 defines internal component boundaries, dependency structures, and cross-module interactions governed by **SOLID principles and Clean Architecture Lite**:

##### 1. Clean Architecture Lite Layering & Dependency Flow
To maintain Pythonic simplicity without heavyweight over-engineering, code is structured into three concentric layers:
```text
src/
├── domain/       # Pure immutable business models (frozen=True) & logic (Zero external deps)
├── services/     # Application use-case orchestration (Depends only on Domain and Protocols)
└── adapters/     # Concrete implementations (CLI parsers, DB connectors, HTTP clients, I/O)
```
- **Strict Inward Dependency Rule**: Dependencies must only point inward (`adapters` $\rightarrow$ `services` $\rightarrow$ `domain`). Importing outer modules from inner layers is blocked by linting and AST analysis.

##### 2. Pydantic v2 Strict Typing & Layer Isolation
- **Boundary Validation (Adapters & Services)**: External inputs (CLI args, HTTP payloads, `config.yaml`) must be rigorously validated using **Pydantic v2 (`BaseModel`, `Field(..., strict=True)`)** and `pydantic-settings`. Untyped `dict` payloads and `Any` types are completely banned.
- **Domain Immutability**: Domain models use immutable value objects (`BaseModel(frozen=True)` or `@dataclass(frozen=True)`), preventing accidental in-place state mutation.

##### 3. Custom Exception Hierarchy & Error Propagation
- Standardizes on a typed domain exception tree deriving from a project root (`AppError`):
  - `DomainError(AppError)` $\rightarrow$ `EntityNotFoundError`, `BusinessRuleViolationError`
  - `AdapterError(AppError)` $\rightarrow$ `ExternalAPIError`, `ConfigurationError`
- AI models must not write `raise Exception("...")` or catching broad `except Exception:` without explicit re-raising.

##### 4. Explicit Sync vs. Async Policy (Zero Function Color Drift)
- Every component must explicitly declare its concurrency model in Gate 3:
  - **Pure Synchronous**: Recommended for CLI utilities, data batch scripts, and simple services.
  - **Pure Asynchronous**: Mandated for high-concurrency I/O and ASGI Web servers.
  - Mixing `sync` and `async` inside the same service layer without explicit thread pool offloading is a Fatal Flaw.

##### 5. Structured Logging & Print Prohibition
- Raw `print()` statements are blocked by `ruff` (`T201`).
- All logging must use standard structured loggers (`logging.getLogger(__name__)` or `structlog`) with structured key-value context (`logger.info("event", extra={...})`).

##### 6. SOLID Architecture Review Matrix (Enforced at Gate 3 Review)
Every `03_architecture.md` must satisfy the following checklist:
- **Single Responsibility (SRP)**: Reject "God Classes" (`Manager`, `CommonService`). A component's role must be definable in one sentence without conjunctions ("and", "also").
- **Open/Closed (OCP)**: Multi-branch conditionals (`if-elif-else`) for extensible features must be refactored into strategy dictionaries or injected protocol handlers.
- **Liskov Substitution (LSP)**: Protocols must explicitly declare return types and raised exceptions. Mocks and production implementations must be 100% interchangeable.
- **Interface Segregation (ISP)**: Standardize on lean, role-specific `typing.Protocol` definitions (1–3 focused methods per protocol).
- **Dependency Inversion (DIP)**: High-level services must never instantiate concrete I/O classes. All external adapters must be supplied via **Constructor Dependency Injection (DI)**.
- **KISS Balance (Rule of Three)**: Zero gratuitous abstraction. If an internal class has only one concrete implementation and is not an external I/O boundary, creating a protocol is prohibited.

##### 7. Integration Test Scope (`03_integration_tests.md`)
- Targets the boundary between `services/` and `adapters/`, validating type transformations across boundaries and safe transactional rollback on adapter failure.

##### 8. DAG Task Decomposition (`tasks.md`)
- Translates the architecture into a Directed Acyclic Graph (DAG) of discrete vertical implementation slices ensuring PR diffs stay under target limits (target <= 400 lines).

##### 9. Gate 3 Red Teaming Personas
- Evaluated by **Principal Architect** (Coupling, SOLID compliance, dependency hygiene) and **Integration QA Engineer** (Contract tests, rollback sanity).

#### Gate 4: Detailed Class Design, Unit Test Scaffold Lock & Human Sign-off
Gate 4 creates the final concrete blueprint and locks the tests before `src/` is unlocked:
- **Complete Class & Method Signatures (`04_detail_design.md`)**:
  - Full type-annotated signatures for all classes, methods, and functions including Pydantic models.
  - Explicit algorithm workflows, error states, and external library call paths.
- **Unit Test Scaffold Formulation (`tests/`)**:
  - Concrete test files created in `tests/` with `@pytest.mark.requirement("REQ-xxx")` tags.
  - Test function names, `@pytest.mark.parametrize` matrices, boundary values (`0`, `-1`, `None`, empty string, max length), and specific expected assertions.
  - Production code in `src/` remains empty (`pass` or `raise NotImplementedError`).
- **Test Scaffold Freeze (Anti-Tautology Lock)**:
  - The test scaffold is committed to Git at Gate 4 completion.
  - `PreToolUse` hook intercepts and blocks any attempt to weaken assertions, loosen Pydantic validation, or delete test cases during Gate 5 implementation.
- **QA Boundary & Equivalence Review**:
  - Evaluated by **QA Engineer** (Boundary value analysis, equivalence partitioning, custom exception coverage) and **Senior Programmer** (YAGNI, over-engineering elimination).
- **TL;DR Human Sign-off Protocol (`05_decision.md`)**:
  - PM-AI generates the 3-Pole Multi-Option Matrix and a 3-line executive summary.
  - Presents 3 mandatory sign-off checkboxes (Option selection rationale, Config schema changes, Accepted risks).
  - Human executes `/gov-signoff` to record Git signature and unlock `src/` editing permissions in `state.json`.

#### Gate 5: Coding, Test Refinement, Differential Coverage & PR Merge Governance
Once Gate 4 human sign-off unlocks `src/`, Gate 5 runs the mechanical implementation and verification cycle to completion:
- **TDD Implementation Execution**:
  - PM-AI implements production logic in `src/` solely to turn the frozen Gate 4 unit test scaffolds green.
  - Attempting to loosen assertions or alter test parameters in `tests/` is intercepted and blocked by `PreToolUse`.
- **Branch Differential Coverage (Strict `--cov-branch` >= 90%)**:
  - Requires >= 90% branch coverage specifically across modified lines via `diff-cover`.
  - Exception and error-handling blocks covering the Gate 2 Mandatory Failure Matrix (timeouts, 429, malformed data, upstream outages) must be affirmatively exercised.
- **Automated Mechanical Audit Suite (`06_qa_report.json`)**:
  - Must pass all mechanical gates: `ruff` (cyclomatic complexity <= 10), `pyright` (strict mode: zero `Any`), `jscpd` (0% duplicate code), and `vulture` (zero unreferenced dead symbols).
  - `gov trace-check` runs AST validation confirming 100% mutual correspondence between `[REQ-xxx]` tags and test decorators.
- **Context-Preserving PR Description Generation (`gov pr-summary`)**:
  - To eliminate reviewer fatigue, PM-AI generates a standardized PR description:
    1. Direct link to requirement `[REQ-xxx]`.
    2. Selected 3-pole option rationale and accepted tradeoffs.
    3. Mechanical QA metrics summary (coverage %, duplication %, complexity).
    4. "Where to Review": Highlighting the core 50 lines of business logic rather than boilerplate.
- **Post-Merge Lifecycle Cleanup (`gov complete`)**:
  - Upon merge to `main`, `state.json` marks the requirement as `COMPLETED`.
  - `unlocked_paths` is immediately reset to empty, re-locking `src/` until the next requirement achieves Gate 4 human approval.
  - Deletes transient feature branches and archives `.specs/` logs.

### 2.2 Cross-Cutting Safety & Governance Protocols

The following systemic protocols operate horizontally across all gate boundaries to ensure safety, consistency, and clean operational recovery:

#### 2.2.1 Upstream Drift Suppression Double-Barrier (Mandatory for Gates 2, 3, and 4)
To structurally prevent "Spec Drift"—where downstream designs silently diverge from upstream requirements—every downstream phase (Gates 2, 3, and 4) must pass a two-tier verification before promotion:

1. **Barrier 1: In-Process Self-Audit (Self-Trace Matrix)**:
   - The authoring agent (PM-AI) must append an **"Upstream Requirement Traceability Matrix"** to the deliverable:
     - Explicitly maps every parent requirement (`[REQ-xxx]`) to the specific section in the current design and its counterpart test case.
     - Mandatory self-declaration of any scope modifications: Any newly introduced capability not present in parent specifications must be flagged as `[SCOPE_EXTENSION]`.
2. **Barrier 2: Independent Third-Party Adversarial Drift Audit (Peer Review)**:
   - Conducted by an **independent auditor subagent** with an isolated conversation context (zero cognitive contamination from the authoring PM-AI).
   - *Audit Focal Questions*:
     1. **Omission Check**: Did the current design drop or weaken any requirement or acceptance scenario from Gate 1/2?
     2. **Phantom Scope Check**: Did the author introduce unrequested features, speculative abstractions, or out-of-scope APIs?
     3. **Option Alignment**: Does the implementation adhere to the 3-pole option chosen in the parent gate?
   - The third-party auditor outputs a structured review (`drift_audit.json`). Any unresolved fatal drift results in an automatic gate check failure (`gov gate-check` exit code `1`).

#### 2.2.2 Conditional Spiral Prototyping (Triggered Only by Technical Uncertainty)
To maintain high development velocity without dogmatic process overhead:
- **Not Mandatory for Standard Tasks**: Routine CRUD, internal business logic, or familiar stack changes skip prototyping and proceed immediately to design.
- **Trigger Conditions (Max 3 Loops in `sandbox/`)**: Prototyping is reserved for:
  1. Evaluating newly introduced external dependencies not currently in `pyproject.toml`.
  2. Verifying unverified third-party API contracts or undocumented payload behaviors.
- Temporary spikes run in `sandbox/` and are excluded from Git production tracking.

#### 2.2.3 Reverse Escalation Protocol (Downstream-to-Upstream Rollback)
When downstream implementation (Gate 5) or detailed design (Gate 4) uncovers that upstream design assumptions are technically impossible, unviable, or unacceptably degrading:
- **No Code-First Patching**: The agent must not silently hack workarounds in code while leaving upstream specifications out of sync.
- **Rollback Mechanics via `gov escalate`**:
  1. *Escalation Filing*: Agent or developer invokes `gov escalate --to-gate [1-3] --reason "<rationale>"`.
  2. *Workspace Re-lock*: `state.json` rolls back `current_gate` to the designated upstream gate. `PreToolUse` immediately re-locks `src/`, preventing product code edits while upstream designs are in flux.
  3. *Audit Log Creation*: Generates a structured escalation record (`.specs/REQ-xxx/escalations/ESC-NNN.json`) documenting the technical blocker, affected requirements, and proposed revision options.
  4. *Upstream Re-Gate & Human Consultation*: Upstream specifications and counterpart tests are updated with a formal revision entry. If the escalation modifies Gate 1 business scope or acceptance criteria, a direct human inquiry is triggered.
  5. *Test Scaffold Realignment*: Once upstream re-approval is secured, downstream test scaffolds and contracts are refreshed, and human sign-off (`05_decision.md`) is re-acquired before `src/` is unlocked again.

#### 2.2.4 Decision Drafting by Lead Agent (PM-AI) & Human Escalation (Skin in the Game)
- The **Lead Agent (PM-AI)** manages the development context, autonomously resolves technical decisions without unnecessary friction, and drafts the structured decision summary (`05_decision.md`) utilizing the 3-Pole Multi-Option Matrix.
- If a tradeoff involves significant business impact, severe technical debt, or external policy constraints, PM-AI generates a direct inquiry to the human operator.
- **Final Approval (Sign-off)** must be explicitly performed by a human (Development Lead / Product Owner) on a UI such as a GitHub PR before Gate 5 implementation unlocks.

#### 2.2.5 Bidirectional Traceability (Ensuring Upper/Lower V-Model Consistency)
- Verifies a consistent traceability chain from Requirements Definition (`REQ-xxx`) through Acceptance Tests (`.feature`), Detailed Design, and Unit Test Code (`@pytest.mark.requirement("REQ-xxx")`).
- Blocks builds and merges upon detecting unauthorized implementations not present in the design (scope creep) or requirements lacking tests (unfulfilled requirements).

### 2.3 Structural Mitigation of 5 Universal Software Engineering Distortions

Beyond specification drift, real-world development projects frequently suffer from five structural distortions where high-speed development degrades into technical bankruptcy. This framework applies mechanical guardrails to eliminate each distortion at its root:

| Universal Distortion | Root Cause in AI/Team Development | Failure Impact | Architectural & Mechanical Countermeasure |
| :--- | :--- | :--- | :--- |
| **1. Tautological Testing** | AI modifies test assertions and expected values to artificially match faulty implementations just to make CI green. | False confidence; 100% test coverage yet catastrophic runtime failures. | **Test Scaffold Lock (Gate 4 $\rightarrow$ 5 Barrier)**: Test scaffold files, assertions, and parameterized cases are frozen prior to implementation. Altering test expectations during Gate 5 is intercepted by `PreToolUse`. |
| **2. Patch-on-Patch Decay (Spaghetti Patching)** | Applying localized `if-else` band-aids without inspecting holistic component architecture. | Exploding cyclomatic complexity, unmaintainable control flow, fragile regressions. | **Complexity & Duplication Ceilings**: Hard block on functions with cyclomatic complexity $> 10$ (`ruff`) and no duplicate blocks (`jscpd` in this outline; the repository uses `scripts/check_duplicates.py`). Enforces SOLID refactoring over patching. |
| **3. Works-on-My-Machine (Env Drift)** | Undocumented local OS tools, global virtualenvs, unpinned packages, and OS-specific path separators. | Builds break immediately on clean CI runners, production containers, or peer machines. | **Hermetic Single-Source Environment**: Mandatory `uv.lock` lockfile verification (`uv lock --check`) on pre-push. All configuration is externalized into typed Pydantic schemas. |
| **4. Zombie Code & Orphaned Tests** | Leaving obsolete functions, commented-out dead code, or unmaintained tests "just in case" during refactoring. | Context window dilution; AI models hallucinate by reading stale code artifacts. | **Dead Code Removal**: AST-level unreferenced symbol detection (`vulture`) and git rejection of commented-out code blocks. Purges orphaned test cases. |
| **5. Mock Drift (Contract Hallucination)** | Manually written mock objects that drift away from true upstream API response structures. | Integration tests pass locally while real HTTP requests crash in production. | **Schema-Driven Fixture Synchronization**: Mocks must be generated from or validated against OpenAPI/JSON schemas rather than fabricated ad-hoc by LLMs. |

### 2.4 System & Non-Functional Requirements

- **Distribution Format (Independence)**:
  Governance rules, prompts, and verification scripts are centrally managed in an independent shared repository (`jtc-gov`) and can be injected into target development repositories as a CLI tool (`gov`).
- **Local Blocking (Inner Loop)**:
  Uses Git `pre-commit` hooks and command execution hooks to evaluate syntax, types, diff coverage, and duplicate code, rejecting commits upon violation.
- **Remote Blocking (Outer Loop)**:
  Integrates with GitHub Actions and standard GitHub Branch Protection / Rulesets to make merging impossible without human approval and all-GREEN CI checks.

---

## 3. Basic Design (System Architecture)

### 3.1 Overall Architecture Overview

This platform consists of **4 Control Layers**:

```text
[Layer 1: Protocol]  Spec Kit-style File State Machine (under .specs/)
        │            (Paired management of each design doc + counterpart test spec)
        │
[Layer 2: Policy]    CLAUDE.md / Per-Gate Red Teaming Prompt Templates
        │
[Layer 3: Control]   Claude Code Permission & Tool Execution Control (Phase-based file edit restrictions)
        │
[Layer 4: Gate]      Python Hooks (pre-commit, Ruff, diff-cover, trace-check, gov CLI)
```

### 3.2 Standard Directory Structure (Target Development Repository)

Upstream designs and test specifications stack in 1-to-1 pairs, with Red Teaming logs (`reviews/`) placed at each boundary. Runtime-agnostic governance uses `AGENT.md` as the canonical policy, with adapter symlinks/generators for specific LLM CLI runtimes (e.g. `CLAUDE.md`).

```text
target-repo/
├── .specs/                          # [Layer 1: Protocol] State and Deliverables
│   ├── REQ-2026-001/
│   │   ├── 01_req_spec.md              # [Gate 1] Requirements Definition Document
│   │   ├── 01_acceptance_tests.feature # [Gate 1] Counterpart: Acceptance Test Spec (BDD/Gherkin)
│   │   ├── 01_gate_reviews/            # [Gate 1] Legal, Finance, CPO, COO Reviews (JSON)
│   │   │
│   │   ├── 02_system_design.md         # [Gate 2] Basic / System Design Document
│   │   ├── 02_system_tests.md          # [Gate 2] Counterpart: System / Non-functional Test Plan
│   │   ├── 02_gate_reviews/            # [Gate 2] SRE & Security Reviews (JSON)
│   │   │
│   │   ├── 03_architecture.md          # [Gate 3] Functional / Component Design Document
│   │   ├── 03_integration_tests.md     # [Gate 3] Counterpart: Integration Test Specification
│   │   ├── 03_gate_reviews/            # [Gate 3] Architect Review (JSON)
│   │   │
│   │   ├── 04_detail_design.md         # [Gate 4] Detailed / Class Design Document
│   │   ├── 04_unit_test_scaffold/      # [Gate 4] Counterpart: Unit Test Scaffolds (Case Definitions)
│   │   ├── 04_gate_reviews/            # [Gate 4] QA & Senior Programmer Reviews (JSON)
│   │   │
│   │   ├── 05_decision.md              # CEO Ruling Draft + Human Approval Metadata (Sign-off)
│   │   └── 06_qa_report.json           # [Gate 5] Implementation, Test Refinement & Traceability Verification Log
│   └── state.json                   # Current Active Phase Management
├── .agent/                          # [Vendor-Neutral Control Directory]
│   ├── settings.json                # Universal Hook configurations
│   └── commands/                    # Slash commands (/gov-status, /gov-redteam, etc.)
├── AGENT.md                         # [Layer 2 & 3: Universal Policy & Philosophy]
├── CLAUDE.md                        # Adapter / Symlink to AGENT.md (for Claude Code runtime)
├── .claude/                         # Adapter directory pointing to .agent/ commands & hooks
├── .pre-commit-config.yaml          # [Layer 4: Gate] Local Deterministic Blocking
├── pyproject.toml                   # Python Config (Ruff, Pyright, pytest)
├── src/                             # Production Code (Uneditable until Gate 4 human approval)
└── tests/                           # Test Code (@pytest.mark.requirement mandatory)
```

### 3.3 MECE Taxonomy of Agent Control Mechanisms (Defense-in-Depth Model)

To reliably govern autonomous coding agents without relying on "wishful instructions", control mechanisms must be structured orthogonally across intervention points—ranging from OS execution privileges to cognitive prompting.

| Control Layer | Mechanism | Intervention Timing | Enforcement Strength (Bypass Resistance) | Primary Responsibility & Design Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **L0: OS / Runtime** | **Permissions & Tool Whitelisting** | Pre-tool invocation (OS level) | **Fixed by the OS or runtime**<br>(the agent cannot override it from inside the session) | - Prohibit destructive shell execution (`sudo`, `rm -rf`, uncontrolled egress).<br>- Provide whitelisted tool sets. |
| **L1: Interception** | **Runtime Hooks** (`PreToolUse`, `PostToolUse`) | Milliseconds before/after tool invocation | **Interception**<br>(Claude Code blocks a tool call only on exit code `2`; exit code `1` does not block, measured 2026-10-26) | - Real-time file access control (e.g. aborting any edit to `src/` prior to Gate 4 sign-off).<br>- Dynamic validation of tool argument payloads. |
| **L2: State / Data** | **State Machine** (`state.json` & JSON Schemas) | State transition & verification | **Deterministic**<br>(Checkable by tools) | - Canonical Single Source of Truth for active requirement, current gate, and `unlocked_paths`.<br>- Completely independent of model memory or conversational drift. |
| **L3: Workflow** | **Skills & Slash Commands** (`.agent/commands/`) | Triggered by user or agent | **Procedural Framing**<br>(Template & format standardization) | - Encapsulate complex operations (`/gov-pair`, `/gov-redteam`, `/gov-advance`) into predictable, reproducible routines.<br>- Eliminate prompt ambiguity during gate generation. |
| **L4: Cognition** | **AGENT.md / System Instructions** | Every conversation turn | **Cognitive Guidance**<br>(Advisory; vulnerable to drift) | - Behavioral guidelines: YAGNI philosophy, search-before-write, code-style ethos.<br>- Guides *how* the agent thinks, not *whether* physical boundaries exist. |
| **L5: Inner Verification** | **Git Hooks** (`pre-commit`) | Commit creation time | **Deterministic Local Blocker** | - Static syntax, typing (`pyright`), duplicate code (`jscpd`), coverage (`diff-cover`), and traceability AST matching (`gov trace-check`). |
| **L6: Outer Verification** | **Remote CI & Human Sign-off** (GitHub) | PR creation & merge time | **Organizational Gatekeeper** | - Human code owner approval (Required Review).<br>- LLM Red Teaming audit log verification on independent CI runners. |

### 3.4 Philosophy of Mechanism Segregation

1. **Never Delegate Security or Permissions to Prompts (`AGENT.md`)**:
   - *Anti-Pattern*: Writing *"Please do not modify `src/` until Gate 4 is approved"* in `AGENT.md`. Models easily violate this when complex contexts or external prompts demand quick fixes.
   - *Proper Separation*: `AGENT.md` navigates priorities (*"Focus on test specifications during Gate 1-4"*), while the `PreToolUse` Hook blocks the tool call if `src/` is touched.
2. **Skills Standardize Procedures; State Governs Outcomes**:
   - *Anti-Pattern*: Relying on natural language prompts to perform adversarial reviews on demand.
   - *Proper Separation*: Skills (`/gov-redteam`) execute the exact review routine, and the data schema (`gate_review.schema.json`) deterministically validates the output before state transition.
3. **Runtime-Agnostic Core (`AGENT.md` over Vendor Lock-in)**:
   - The framework treats `AGENT.md` and `.agent/` as standard specifications. Run-time specific configurations (`CLAUDE.md`, `.claude/settings.json`, Cursor rules, etc.) act as generated adapters that point to the underlying `gov` CLI and protocol.

### 3.5 GitHub Toolkit Integration Strategy & Red Teaming Evaluation

To leverage proven industry standards without compromising governance integrity, this framework incorporates core capabilities from **GitHub Next's Spec Kit (`github/spec-kit`)** and **GitHub CLI (`gh`)**.

#### 3.5.1 Dual-Persona Red Teaming Evaluation
Prior to adoption, the integration strategy was subjected to adversarial review by two opposing specialized personas (limited to max 2 fatal flaws each):

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Persona A: Platform Engineer / SRE                                                     │
│ - Fatal Flaw 1 (Network Dependency in Local Hooks): Calling `gh` in local git hooks    │
│   (pre-push) introduces network latency and breaks offline operation.                  │
│ - Fatal Flaw 2 (Version Drift via uvx): Unpinned `uvx --from git+...` causes           │
│   divergent governance versions across developer environments.                         │
│ - Status: REJECTED (Resolved via Section 3.5.2)                                        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Persona B: Software Architect / Security Lead                                          │
│ - Fatal Flaw 1 (Fork & Internalize Anti-Pattern): Direct schema internalization of     │
│   Spec Kit leads to upstream drift and maintenance debt. Must use Decorator pattern.   │
│ - Fatal Flaw 2 (Context Pollution / Privilege Escalation): Local hooks executing `gh`  │
│   confounds the Inner Loop with the Outer Loop, exposing credential attack surfaces.   │
│ - Status: REJECTED (Resolved via Section 3.5.2)                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 3.5.2 Refined Architectural Integration Strategy
In response to the Red Teaming audit, the integration is governed by the following three architectural constraints:

1. **Strict Inner Loop / Outer Loop Air Gap (Offline Local Determinism)**:
   - **Inner Loop (Local Hooks: `PreToolUse`, `pre-commit`, `pre-push`)**: Network-isolated. Executes zero `gh` API calls. Relies exclusively on local files (`.specs/state.json`, local Git commits, local AST parsing, local `pytest`). Execution latency guaranteed under 200ms.
   - **Outer Loop (Remote CI & PR Gate: GitHub Actions)**: The GitHub CLI (`gh`) and Octokit are delegated exclusively to the remote CI environment for posting Red Teaming PR comments, verifying required branch rulesets, and validating human reviewer sign-off.
2. **Pinned Version Governance (Zero Drift Deployment)**:
   - Eliminates unpinned `uvx` executions. `jtc-gov` is declared as a pinned dependency in the target repository's `pyproject.toml` (`jtc-gov == X.Y.Z`).
   - Initialization and runtime execution are invoked deterministically via `uv run gov <command>`.
3. **Decorator Architecture for Spec Kit Protocols**:
   - Rather than maintaining an internal fork of Spec Kit markdown formats, `jtc-gov` wraps Spec Kit deliverables (`spec.md`, `tasks.md`) via a non-invasive Decorator pattern, attaching V-Model counterpart test specifications (`*_tests.md`) and structured audit reviews (`*_gate_reviews/`) as adjacent, companion assets.

| Component / Pattern | Upstream Source | Integration Strategy | Local / Remote Boundary |
| :--- | :--- | :--- | :--- |
| **Scaffolding CLI** | `github/spec-kit` | `gov init` generates `.specs/`, `.agent/`, and local hook bindings | Local (Pinned via `pyproject.toml`) |
| **Ambiguity Extraction** | `github/spec-kit` | Mandatory "Clarification Checklist" injected into Gate 1 spec | Local (`01_req_spec.md`) |
| **DAG Task Decomposition** | `github/spec-kit` | Task dependency graph enforcing 400-line blast radius limit | Local (`04_detail_design.md` & `tasks.md`) |
| **PR & Sign-off Audit** | GitHub CLI (`gh`) | Verification of GitHub Required Reviews and branch rulesets | Remote (`.github/workflows/gate-ci.yml`) |
| **Audit Log Posting** | GitHub Actions Toolkit | Automated bot comments posting structured Red Teaming JSON summaries | Remote (`actions/github-script`) |

---

## 4. Detailed Component Design

### 4.1 Protocol Design (Deliverable Schemas)

Defines deliverables and state models for all gates using JSON Schema so hooks can determine pass/fail status without relying on prompt instructions alone.

#### 4.1.1 State Management Schema (`.specs/state.json`)
Tracks the active feature/requirement lifecycle, the active gate, and white-listed paths permitted for modification in the current phase.

```json
{
  "$schema": "./state.schema.json",
  "active_requirement_id": "REQ-2026-001",
  "requirements": {
    "REQ-2026-001": {
      "current_gate": "GATE1_SPEC",
      "status": "IN_PROGRESS",
      "unlocked_paths": [
        ".specs/REQ-2026-001/01_*"
      ],
      "completed_gates": []
    }
  }
}
```
* **Enforcement Rule**: Any file modification outside `unlocked_paths` is intercepted and blocked at the tool execution level (`PreToolUse` hook) and commit level (`pre-commit`).

#### 4.1.2 Generic Pair Review Deliverable (`gate_review.schema.json`)
Every adversarial persona (human or LLM subagent) must output an audit deliverable adhering to this schema.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GateReviewDeliverable",
  "type": "object",
  "required": [
    "gate_id",
    "requirement_id",
    "reviewer_persona",
    "status",
    "design_flaws",
    "test_design_flaws",
    "accepted_tradeoffs",
    "reviewed_at"
  ],
  "properties": {
    "gate_id": {
      "type": "string",
      "enum": ["GATE1_SPEC", "GATE2_SYSTEM", "GATE3_INTEGRATION", "GATE4_DETAIL", "GATE5_IMPL"]
    },
    "requirement_id": {
      "type": "string",
      "pattern": "^REQ-[0-9]{4}-[0-9]{3,}$"
    },
    "reviewer_persona": {
      "type": "string",
      "enum": ["LEGAL", "FINANCE", "CPO", "COO", "SRE", "SECURITY", "ARCHITECT", "QA", "SENIOR_DEV", "AUTO_AUDIT"]
    },
    "status": {
      "type": "string",
      "enum": ["APPROVED", "REJECTED"]
    },
    "design_flaws": {
      "type": "array",
      "maxItems": 2,
      "items": { "type": "string" },
      "description": "Fatal flaws found in the design deliverable (Max 2 to avoid bureaucratic inflation)."
    },
    "test_design_flaws": {
      "type": "array",
      "maxItems": 2,
      "items": { "type": "string" },
      "description": "Fatal flaws found in the counterpart test specification (Max 2)."
    },
    "accepted_tradeoffs": {
      "type": "array",
      "items": { "type": "string" }
    },
    "reviewed_at": {
      "type": "string",
      "format": "date-time"
    }
  },
  "additionalProperties": false
}
```

#### 4.1.3 Multi-Option Decision Framework & CEO Sign-off (`05_decision.md`)
AI models tend to struggle with generating truly diverse alternatives, defaulting to one obvious proposal and two superficial strawmen. To enforce actionable decision-making for both PM-AI and humans, the framework mandates an **Orthogonal Polar-Axis Multi-Option Generation** protocol:

##### Mandatory 3-Pole Option Architecture
Every architectural or requirement decision must formulate at least 3 distinct options forced along competing design philosophies:
1. **Option A (Ultra-Conservative / KISS Pole)**:
   - *Ethos*: Zero new dependencies, minimal edits to existing code, battle-tested patterns.
   - *Evaluation*: Lowest regression risk, but potential tech debt or manual boilerplate.
2. **Option B (Industry De-Facto / Standard Pole)**:
   - *Ethos*: Standard ecosystem libraries (e.g. Pydantic, FastAPI, Click), standard best practices.
   - *Evaluation*: High developer familiarization and rapid velocity, moderate dependency footprint.
3. **Option C (Radical Optimization / Scalable Pole)**:
   - *Ethos*: Event-driven, fully asynchronous, pluggable architecture, maximum future-proofing.
   - *Evaluation*: Highest extensibility, but introduces cognitive load and potential YAGNI overhead.

##### Structure of `05_decision.md`:
```markdown
# CEO Ruling & Ringi Draft: REQ-2026-001

## 1. Executive Summary & Context
- **Feature**: Summary of proposed functionality
- **Gate 1-4 Review Status**: Single-turn Red Teaming completed. PM-AI resolved minor items; critical tradeoffs escalated below.

## 2. Multi-Option Comparison Matrix (Mandatory Pro/Con/Risk)

| Dimension | Option A (KISS Pole) | Option B (Standard Pole) | Option C (Scalable Pole) |
| :--- | :--- | :--- | :--- |
| **Architectural Concept** | Pure standard library, zero deps | Pydantic v2 + Click CLI | Async plugin-based architecture |
| **Pros (Merits)** | Zero bundle bloat, zero CVE risk | Rapid parsing, rich validation | Infinite runtime extensibility |
| **Cons (Demerits)** | High manual validation boilerplate | Adds 2 external dependencies | High initial complexity / YAGNI |
| **Accepted Risks** | Maintenance burden if spec expands | Version upgrade friction | Over-engineering for MVP |

## 3. Recommended Choice & Rationale (PM-AI Recommendation)
- **Selected Option**: Option B (Standard Pole)
- **Rationale**: Balances schema rigor with simplicity without triggering premature optimization.

## 4. Scope Boundary Definition (YAGNI Lock)
- Explicit list of prohibited fallbacks, interfaces, and unrequested abstractions.

---
## 5. Human Sign-off (Mandatory)
<!-- Human Operator verifies the comparison matrix and signs below -->
HUMAN_SIGN_OFF: APPROVED by @username at YYYY-MM-DDTHH:MM:SSZ
```

---

### 4.2 Shared CLI (`gov`) Verification Logic Design

A Python command-line tool distributed from the shared governance repository.

| Command | Execution Timing | Responsibility & Verification Details |
| :--- | :--- | :--- |
| `gov init` | Project Initialization | Creates `.specs/` structure and deploys `.claude/` hooks/skills and `pre-commit` configurations. |
| `gov gate-check --gate [1-5]` | At Each Gate Transition / `pre-commit` | 1. **Pair Check**: Confirms both design doc and counterpart test spec exist and are non-empty.<br>2. **Review Check**: Validates that all required persona reviews for the gate match `gate_review.schema.json` and have `status: APPROVED`.<br>3. **Promotion**: On pass, updates `state.json` (`current_gate` and `unlocked_paths`). On fail, exits with code `1`. |
| `gov trace-check` | Detailed Design & Implementation Completion / CI | 1. Extracts requirement tags (`[REQ-xxx]`) from `01_req_spec.md`.<br>2. Inspects `tests/` AST for `@pytest.mark.requirement("REQ-xxx")` decorators.<br>3. Detects under-coverage (missing tests) or scope drift (tests/code without requirement tags). Exits `1` on mismatch. |
| `gov verify-tool --file <path>` | Real-time (`PreToolUse` Hook) | Checks whether the target file modification is allowed under current `state.json.unlocked_paths`. Aborts tool execution immediately if unauthorized. |
| `gov escalate --to-gate [1-3]` | Technical Blocker in Downstream | Re-locks `src/`, reverts `state.json.current_gate` to target upstream gate, and initializes an `ESC-NNN.json` escalation record. |
| `gov pr-summary` | PR Creation / CI | Auto-generates standardized PR description linking REQ-xxx, 3-pole tradeoffs, QA metrics, and 50-line review highlights. |
| `gov complete` | Post-Merge to `main` | Marks requirement as `COMPLETED` in `state.json`, resets `unlocked_paths` to re-lock `src/`, and archives `.specs/` logs. |

---

### 4.3 External Skill Sandboxing

To allow developers to install external Claude skills or community prompt libraries in the future without compromising governance integrity:
1. **OS/Hook Level Sovereignty**: External skills cannot bypass `PreToolUse` and `pre-commit` verification regardless of prompt instructions.
2. **Phase-Scoped Tool Activation**: Implementation-oriented skills (e.g. code generation, refactoring) are only enabled when `current_gate == GATE5_IMPL` and human sign-off exists.

---

### 4.4 Claude Code Control & Extension Design (Layer 2 & 3)

Combines top-level declarative policy (`CLAUDE.md`), execution interception (`PreToolUse` Hook), and structured workflow commands (`.claude/commands/`).

#### 4.4.1 Real-Time Interception Hook (`.claude/settings.json`)
Claude Code supports hook scripts triggered before tool execution. When Claude attempts to run `Edit`, `Write`, or `MultiEdit`, the `PreToolUse` hook intercepts the operation before file modification occurs on disk.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "command": "gov verify-tool --tool \"$CLAUDE_TOOL_NAME\" --input \"$CLAUDE_TOOL_INPUT_JSON\""
      }
    ]
  }
}
```

* **Execution Behavior**:
  1. `gov verify-tool` parses the target file path from `$CLAUDE_TOOL_INPUT_JSON`.
  2. Compares the path against `state.json.requirements[active_id].unlocked_paths`.
  3. **Unauthorized Path (e.g. `src/` touched before Gate 4 human sign-off)**: Exits with code `2` (the code Claude Code treats as blocking) and returns a structured stderr error message explaining the violation:
     > `[GOVERNANCE ERROR] Editing 'src/service.py' is blocked in GATE1_SPEC. You must complete Gate 1-4 and acquire human sign-off in 05_decision.md before modifying product code.`
  4. Claude Code receives the failure output and aborts the tool call, preventing unauthorized file writes before they touch disk.

#### 4.4.2 Dedicated Governance Workflow Skills / Slash Commands (`.claude/commands/`)
Distributed by `gov init` to standardize interactions and eliminate ad-hoc, uncontrolled prompting.

| Command / Skill | Invocation Role | Action & Operational Guarantees |
| :--- | :--- | :--- |
| `/gov-status` | Developer / AI | Reads `.specs/state.json` and displays current gate, active requirement, unlocked paths, and pending approvals. |
| `/gov-pair [gate]` | AI Assistant | Enforces paired template generation. Injects dual skeleton files (e.g., `01_req_spec.md` + `01_acceptance_tests.feature`). |
| `/gov-redteam [gate]` | AI Subagents | Dispatches independent review prompts tailored to the gate's assigned personas. Generates individual review JSONs validated against `gate_review.schema.json`. |
| `/gov-advance` | Developer / CI | Runs `gov gate-check --gate [current]`. If all pair assets exist and all reviews are `APPROVED`, advances `state.json` and unlocks the next phase. |
| `/gov-signoff` | Human Approver | Records the human sign-off signature in `05_decision.md` and verifies integrity before unlocking `src/` for Gate 5. |

#### 4.4.3 Policy Guardrails (`CLAUDE.md`)
Top-level instructions persisted in the root repository to guide model reasoning:
- **Mandatory Paired Creation**: Never produce a design document without its counterpart test specification or test scaffold.
- **Strict YAGNI Penalization**: Reject any speculative abstraction, unreferenced helper function, or unrequested fallback logic.
- **Requirement Traceability**: All test functions written during Gate 4 scaffold and Gate 5 implementation must carry `@pytest.mark.requirement("REQ-xxx")`.

### 4.5 Hook & Verification Design (Python & GitHub)

#### Local Gate (`pre-commit` & Claude PreToolUse Hook)
- `gov verify-tool`: Intercepts tool calls before Claude executes file edits.
- `gov gate-check`: Validates design/counterpart-test pairs and blocks changes that have not passed preceding phase Red Teaming.
- `gov trace-check`: Verifies bidirectional traceability between requirement IDs and test scaffolds/implementations.
- `ruff check` & `ruff format`: Inspects syntax, formatting, and cyclomatic complexity.
- `pyright` (strict mode): Eliminates missing type inferences and `Any`.
- `jscpd src/`: Monitors code duplication rate (blocks copy-paste implementations).
- `diff-cover`: Enforces test coverage (90% or higher) on newly modified lines.

#### Remote Gate (GitHub PR & Actions)
- **Automated Per-Gate Red Teaming**: When a PR for each gate is created or updated, calls LLM APIs via GitHub Actions to generate JSON reviews from the designated persona groups (evaluating both design and counterpart test perspectives) and posts them as PR comments.
- **CEO Summary Drafting**: Automatically updates the PR description by synthesizing comments from each persona.
- **Human Sign-off (Required Review)**: Blocks merging until the designated code owner (human) approves on GitHub.
- **V-Model Traceability Verification**: Runs `gov trace-check` in CI to confirm complete alignment (`GREEN`) between specifications and tests.

### 4.6 Branching Strategy & Pre-Push Quality Discipline (Anti-Patch Governance)

To prevent code degradation, patch-on-patch spaghetti, and orphaned assets during high-speed AI development, strict branch lifecycle rules and pre-push verification gates are established.

#### 4.6.1 Branch Naming & Sizing Limits
- **Branch Naming Standard**:
  - New feature development: `feat/REQ-YYYY-NNN-<short-slug>` (linked to the requirement ID in `.specs/`).
  - Bug fixes: `fix/ISSUE-NNN-<short-slug>`.
  - Refactoring/Governance updates: `refactor/<short-slug>` or `gov/<short-slug>`.
- **Branch Size Upper Bound (Progressive Blast Radius Control)**:
  - **Pragmatic Initial Threshold (Hard Gate)**: To prevent initial development friction while catching unintended or fabricated AI changes, the initial hard block is set at **1,500 net changed lines** (excluding generated mocks, data fixtures, and `.specs/` logs via `.govignore`).
  - **Target Guideline (Soft Review Target)**: Branches are encouraged to remain under **400 net changed lines** and **2 to 3 days** of active lifespan. If a feature naturally expands beyond this, Gate 1 decomposes it into sub-features (`REQ-xxx-F01`, `REQ-xxx-F02`).

#### 4.6.2 Pre-Push Mechanical & Cognitive Audit Checklist (Local CI/CD Simulation)
Prior to pushing to origin or requesting review, both the developer and the AI agent must run the pre-push audit suite (`gov audit-push` or Git `pre-push` hook). **Pushing to origin is rejected by the hook unless all local quality checks and local CI/CD pipelines pass completely (100% GREEN).**

1. **Local CI/CD Dry-Run Execution (Shift-Left CI)**:
   - Before push, the entire CI pipeline is run locally (e.g. via `pytest tests/`, full package build `python -m build`, or local workflow runners like `act`).
   - Any failing test, regression in existing suites, or environment build failure aborts the push instantly. Never rely on remote GitHub Actions to find easily catchable failures.
2. **Documentation Synchronization (No Spec Drift)**:
   - Every modified behavior, schema change, or new CLI option must be accompanied by updates in `doc/`, `README.md`, or the corresponding `.specs/` documents. Code changes without corresponding doc diffs trigger a push rejection.
3. **Dead Code & Obsolete Test Removal (no leftovers)**:
   - When existing functions, classes, or helper methods are superseded by new implementations, the legacy code must be **completely removed** (not commented out or left as unused fallback).
   - Tests covering deprecated or replaced logic must be purged or updated. No orphan tests or ignored (`@pytest.mark.skip`) tests are permitted without explicit rationale.
4. **No Hardcoding & Constant Externalization**:
   - Zero hardcoded magic strings, URLs, credentials, timeouts, or environment-dependent values in `src/`.
   - All runtime variables and configuration constants must be externalized into project-standard configuration files (e.g. `config.yaml`, `.env.example`, or typed `pydantic-settings` schemas).
5. **Holistic Refactoring over Band-Aid Patching (SOLID Principles)**:
   - AI agents tend to append local `if-else` patches or repetitive helper functions rather than refactoring the underlying design.
   - Any modification must satisfy **SOLID Principles**:
     - **Single Responsibility (SRP)**: No bloated multi-purpose modules.
     - **Open/Closed (OCP)**: Extensibility achieved via interfaces/abstractions rather than nested conditionals.
     - **Liskov Substitution (LSP)** & **Interface Segregation (ISP)**: Lean, purposeful interfaces.
     - **Dependency Inversion (DIP)**: High-level modules must not depend on low-level concrete implementations.
   - If an enhancement requires altering component interactions, the agent must perform **holistic structural refactoring** rather than wrapping existing flaws in shallow adapters.

```text
[Developer / AI Agent]
         │
    (1) Git Commit (pre-commit hook: Ruff, Pyright strict, jscpd duplication, diff-cover >= 90%)
         │
    (2) Pre-Push Verification (Git pre-push hook: gov audit-push):
         ├─ [Gate A: Branch & Scope] Branch name == feat/REQ-xxx & Diff <= 400 lines
         ├─ [Gate B: Local CI/CD] Full pytest suite + build packaging executed locally (100% GREEN)
         ├─ [Gate C: Traceability] gov trace-check confirms 100% REQ-to-test AST alignment
         ├─ [Gate D: Doc Sync] Specs and doc/ updated alongside code diffs
         ├─ [Gate E: Dead Code] AST/vulture check confirms zero unreferenced orphan symbols
         └─ [Gate F: Config Check] Regex audit confirms zero hardcoded secrets/magic URLs
         │
    (3) Push permitted only if all gates pass
```

---

## 5. Detailed Implementation Roadmap & Execution Plan

To transition from architectural specification to an operational, battle-tested system, implementation is structured into 4 sequential phases, each governed by its own strict acceptance criteria.

---

### Phase 1: Core CLI & Protocol Engine Development (`jtc-gov`)
*Objective*: Build the standalone Python CLI package (`jtc-gov`) that deterministically enforces the Layer 1 (Protocol) and Layer 4 (Gate) state machine.

1. **Package Setup & Tooling**:
   - Modern `pyproject.toml` setup using `hatchling` or `flit`, pinned via `uv`.
   - Python 3.11+ strict mode, zero heavy dependencies (leverages `click` or `argparse`, `pydantic v2`, `jsonschema`).
2. **Schema & State Engine (`jtc_gov.engine`)**:
   - Implementation of `state.json` lifecycle state machine (`INIT`, `IN_PROGRESS`, `ROLLBACK`, `COMPLETED`).
   - JSON Schema compilation for `gate_review.schema.json` and `escalation.schema.json`.
   - File whitelist path matcher (glob validation for `unlocked_paths`).
3. **Core CLI Commands (`jtc_gov.cli`)**:
   - `gov init`: Scaffolds `.specs/`, `.agent/`, pre-commit hooks, and runtime adapters.
   - `gov new --req <id> --title <slug>`: Creates feature branch and directory structure.
   - `gov verify-tool`: Millisecond-level interceptor for Claude Code `PreToolUse` hooks.
   - `gov gate-check --gate [1-5]`: Multi-gate review verifier and state promoter.
   - `gov trace-check`: AST-based bidirectional validator linking `[REQ-xxx]` to `@pytest.mark.requirement`.
   - `gov escalate --to-gate [1-3]`: Workspace re-locker and state rollback engine.
   - `gov audit-push`: Pre-push multi-gate local CI runner (diff limits, dead code, doc sync).
   - `gov pr-summary` & `gov complete`: PR lifecycle automation and post-merge lock reset.
4. **Acceptance Criteria for Phase 1**:
   - 100% unit and integration test coverage for all `gov` subcommands.
   - Local execution benchmark: `gov verify-tool` completes in under 50ms.

---

### Phase 2: Agent Policy, Hooks & Command Templates (`.agent/`)
*Objective*: Configure Layer 2 (Policy) and Layer 3 (Control) adapters so AI coding assistants (Claude Code, Cursor, etc.) execute within constraints.

1. **Vendor-Neutral Policy & Instructions (`AGENT.md`)**:
   - Clean, comprehensive instructions embedding the 5 Universal Distortions, SOLID guidelines, and TDD execution protocols.
   - Symlink/adapter automation for `CLAUDE.md`.
2. **Interception Hook Configuration (`.agent/settings.json`)**:
   - `PreToolUse` hook definitions binding `Edit|Write|MultiEdit` to `gov verify-tool`.
   - Stderr error formatting guiding the agent when file modification is blocked.
3. **Structured Governance Slash Commands (`.agent/commands/`)**:
   - `/gov-status`: Visualizes active gate, unlocked paths, and pending items.
   - `/gov-pair [gate]`: Injects dual template pairs (Spec + Test Counterpart).
   - `/gov-redteam [gate]`: Dispatches single-turn persona reviews via subagents.
   - `/gov-advance`: Validates gate completion and triggers state promotion.
   - `/gov-signoff`: Interactive human approval interface for `05_decision.md`.
4. **Git Hook Bindings**:
   - Complete `.pre-commit-config.yaml` template configured with Ruff, Pyright, jscpd, and diff-cover.
   - Standalone Git `pre-push` script invoking `gov audit-push`.
5. **Acceptance Criteria for Phase 2**:
   - Claude Code attempting to write `src/service.py` during Gate 1 is blocked and guided itself toward `01_req_spec.md`.

---

### Phase 3: GitHub Actions & Remote CI Integration
*Objective*: Build the Outer Loop gatekeeper ensuring no code merges without human approval, green CI, and full traceability.

1. **Workflow Templates (`.github/workflows/`)**:
   - `gate-verify.yml`: Executes `gov trace-check`, diff-cover >= 90%, and full test suites on every PR push.
   - `redteam-audit.yml`: Automated GitHub Actions workflow triggering independent LLM review runs on PR creation, posting structured reviews as PR comments.
   - `pr-summary.yml`: Automated description decorator posting the 3-pole comparison matrix and 50-line review focus.
2. **Branch Protection & Ruleset Standard**:
   - Configuration template requiring all CI checks green and designated code owner (human) review approval before merge.
3. **Acceptance Criteria for Phase 3**:
   - A mock PR lacking human sign-off or failing `gov trace-check` is blocked from merging by GitHub Rulesets.

---

### Phase 4: Pilot Operation & Dogfooding
*Objective*: Validate the entire V-model pipeline on a real-world Python module from requirements to merge.

1. **Dogfooding Target**:
   - Run the pilot on `jtc-gov` itself or a real companion microservice.
2. **Execution Flow Verification**:
   - Execute Gate 1 (Requirements & Gherkin feature with 3-pole options).
   - Execute Gate 2 (System design, PyPI survey, config schema, mock contract).
   - Execute Gate 3 (Clean Architecture Lite, Pydantic strict models, DAG tasks).
   - Execute Gate 4 (Class design, test scaffold freeze, human `/gov-signoff`).
   - Execute Gate 5 (TDD implementation in `src/`, branch coverage >= 90%, PR merge).
   - Execute intentional Reverse Escalation test (`gov escalate`) to verify workspace re-locking.
3. **Final Polish & Documentation Release**:
   - Incorporate developer experience refinements and publish initial `v0.1.0` release.
# Phase 4 Implementations
Added gov init, gov doctor, gov gate-check, gov draft-decision, gov trace-check, gov escalate
