"""Project Distribution & Scaffolding Engine for jtc-gov."""

import json
from pathlib import Path


def init_project(preset: str = "solo", ci: str | None = None) -> None:
    """Initialize governance structures for the project."""
    # 1. Scaffold .specs/ with canonical state.json
    specs_dir = Path(".specs")
    specs_dir.mkdir(exist_ok=True)
    state_file = specs_dir / "state.json"

    # Initialize basic state machine structure
    state_data = {
        "active_requirement_id": "REQ-INIT-001",
        "requirements": {
            "REQ-INIT-001": {
                "current_gate": "GATE1_SPEC",
                "unlocked_paths": [".specs/REQ-INIT-001/*", "doc/*"],
            }
        },
        "preset": preset,
    }
    state_file.write_text(json.dumps(state_data, indent=2) + "\n", encoding="utf-8")

    # 2. Deploy .agent/settings.json configuring real-time PreToolUse hook
    agent_dir = Path(".agent")
    agent_dir.mkdir(exist_ok=True)
    settings_file = agent_dir / "settings.json"
    settings_data = {
        "hooks": {"PreToolUse": {"command": "uv run gov verify-tool --input '{tool_input}'"}}
    }
    settings_file.write_text(json.dumps(settings_data, indent=2) + "\n", encoding="utf-8")

    # 3. Deploy universal agent constitutions: AGENT.md and CLAUDE.md
    agent_md = Path("AGENT.md")
    if not agent_md.exists():
        agent_md.write_text(
            "# AGENT CONSTITUTION\n\nFollow all jtc-gov rules, zero-tolerance for AI runaway.\n",
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
