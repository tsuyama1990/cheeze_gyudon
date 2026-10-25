Feature: JTC-Style Governance CLI Engine
  As a software engineering lead
  I want a deterministic governance CLI
  So that autonomous AI agents cannot bypass specifications or commit unchecked code

  Scenario: Intercept unauthorized file modification during Gate 1
    Given the active gate in state.json is "GATE1_SPEC"
    When an AI agent attempts to edit "src/service.py"
    Then the "gov verify-tool" command exits with code 1
    And returns an error message containing "[GOVERNANCE ERROR]"

  Scenario: Verify bidirectional requirement traceability
    Given requirement "REQ-2026-001-F01" is declared in "01_req_spec.md"
    And a test marked with "@pytest.mark.requirement('REQ-2026-001-F01')" exists in "tests/"
    When the developer executes "gov trace-check"
    Then the command exits with code 0

  Scenario: Rollback state upon downstream escalation
    Given the active gate is "GATE5_IMPL"
    When the developer executes "gov escalate --to-gate 2 --reason 'API contract change'"
    Then the active gate in state.json is reverted to "GATE2_SYSTEM"
    And "src/" is immediately re-locked from tool modification
