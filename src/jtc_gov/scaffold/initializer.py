"""Project Distribution & Scaffolding Engine for jtc-gov."""

import json
from pathlib import Path

from jtc_gov.domain.legacy_models import GateId, RequirementItem, RequirementStatus, StateModel
from jtc_gov.services.gate_keeper import get_unlocked_paths_for_gate
from jtc_gov.services.state_engine import write_state

INITIAL_REQUIREMENT_ID = "REQ-0000-001"


def init_project(ci: str | None = None) -> None:
    """Initialize governance structures for the project."""
    # 1. Scaffold .specs/ with canonical state.json
    specs_dir = Path(".specs")
    specs_dir.mkdir(exist_ok=True)

    requirement = RequirementItem(
        title="Initial requirement",
        current_gate=GateId.GATE1_SPEC,
        status=RequirementStatus.INIT,
        unlocked_paths=get_unlocked_paths_for_gate(GateId.GATE1_SPEC, INITIAL_REQUIREMENT_ID),
        completed_gates=[],
    )
    write_state(
        StateModel(
            active_requirement_id=INITIAL_REQUIREMENT_ID,
            requirements={INITIAL_REQUIREMENT_ID: requirement},
        )
    )

    # 2. Deploy .agent/settings.json configuring real-time PreToolUse hook
    agent_dir = Path(".agent")
    agent_dir.mkdir(exist_ok=True)
    settings_file = agent_dir / "settings.json"
    settings_data = {
        "hooks": {"PreToolUse": {"command": "uv run gov verify-tool --input '{tool_input}'"}}
    }
    settings_file.write_text(json.dumps(settings_data, indent=2) + "\n", encoding="utf-8")

    # 3. Deploy agent rules: AGENT.md and CLAUDE.md
    agent_md = Path("AGENT.md")
    if not agent_md.exists():
        agent_md.write_text(
            "# AGENT RULES\n\nFollow all jtc-gov rules.\n",
            encoding="utf-8",
        )
    claude_md = Path("CLAUDE.md")
    if not claude_md.exists():
        claude_md.write_text("# CLAUDE SPECIFIC RULES\n\nAdhere to AGENT.md.\n", encoding="utf-8")

    # 4. Configure .pre-commit-config.yaml
    pre_commit_yaml = Path(".pre-commit-config.yaml")
    if not pre_commit_yaml.exists():
        yaml_content = """repos:
  - repo: local
    hooks:
      - id: ruff
        name: ruff
        entry: uv run ruff check
        language: system
        types: [python]
      - id: ruff-format
        name: ruff-format
        entry: uv run ruff format
        language: system
        types: [python]
      - id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        types: [python]
      - id: vulture
        name: vulture
        entry: uv run vulture
        language: system
        types: [python]
      - id: pytest-coverage
        name: pytest-coverage
        entry: uv run pytest --cov-fail-under=90
        language: system
        types: [python]
        stages: [push]
"""
        pre_commit_yaml.write_text(yaml_content, encoding="utf-8")

    # 5. Generate .github/workflows/gate_pipeline.yml if --ci github
    if ci == "github":
        github_dir = Path(".github/workflows")
        github_dir.mkdir(parents=True, exist_ok=True)
        pipeline_file = github_dir / "gate_pipeline.yml"
        pipeline_content = """name: Gate Verification Pipeline
on: [push, pull_request]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install uv
        run: pip install uv
      - name: Run verification
        run: uv run pytest
"""
        pipeline_file.write_text(pipeline_content, encoding="utf-8")
