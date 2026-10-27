# ruff: noqa: PLC0415
"""Command Line Interface for jtc-gov governance framework."""

import json
import subprocess
import sys
from pathlib import Path

import click

from jtc_gov.domain.exceptions import (
    GovernanceError,
    StateNotFoundError,
    TraceabilityMismatchError,
)
from jtc_gov.domain.legacy_models import GateId
from jtc_gov.integrations.github.pr_formatter import format_audit_comment
from jtc_gov.integrations.github.summary_generator import generate_pr_summary
from jtc_gov.services.decision_engine import draft_decision, load_reviews
from jtc_gov.services.escalator import escalate as run_escalate
from jtc_gov.services.gate_keeper import validate_gate
from jtc_gov.services.redteam_engine import run_redteam_gate
from jtc_gov.services.state_engine import read_state
from jtc_gov.services.tracer import verify_traceability
from jtc_gov.services.verifier import verify_tool as run_verify_tool

DEFAULT_VERIFY_TOOL = "Write"

GATE_MAPPING: dict[int, GateId] = dict(enumerate(GateId, start=1))


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """AI-Driven Development Governance CLI (JTC-Style Governance)."""


@main.command()
@click.option("--ci", default=None, help="CI provider (e.g., github)")
def init(ci: str | None) -> None:
    """Initialize governance structures for the project."""
    from jtc_gov.scaffold.initializer import init_project

    init_project(ci=ci)
    click.echo("[GOV] Project initialized successfully.")


@main.command()
def doctor() -> None:
    """Diagnose the local governance environment."""
    from jtc_gov.diagnostics.doctor import run_diagnostics

    run_diagnostics()


@main.command(name="gate-check")
@click.option("--gate", type=int, required=True, help="Gate number to check (1-5)")
def gate_check(gate: int) -> None:
    """Validate deliverables and promote state across Gates 1-5."""
    gate_id = GATE_MAPPING.get(gate)
    if gate_id is None:
        click.echo("Gate must be 1-5", err=True)
        raise SystemExit(1)

    try:
        validate_gate(gate_id)
    except GovernanceError as e:
        click.echo(f"[GOVERNANCE ERROR] {e}", err=True)
        raise SystemExit(1) from e
    click.echo(f"Gate {gate} check passed. State advanced.")


@main.command(name="trace-check")
def trace_check() -> None:
    """AST-based bidirectional validator linking [REQ-xxx] to @pytest.mark.requirement."""
    try:
        verify_traceability()
    except TraceabilityMismatchError as e:
        click.echo(f"[GOVERNANCE ERROR] {e}", err=True)
        raise SystemExit(1) from e
    click.echo("Traceability check passed.")


@main.command()
@click.option("--gate", type=int, required=True, help="Target gate to escalate to")
@click.option("--reason", type=str, required=True, help="Reason for escalation")
def escalate(gate: int, reason: str) -> None:
    """Structured upstream rollback protocol."""
    try:
        run_escalate(gate, reason)
    except (GovernanceError, ValueError) as e:
        click.echo(f"[GOVERNANCE ERROR] {e}", err=True)
        raise SystemExit(1) from e
    click.echo(f"Escalated to Gate {gate}.")


@main.command()
def status() -> None:
    """Show current governance state and active gate."""
    try:
        state = read_state()
        active_req_id = state.active_requirement_id
        if active_req_id not in state.requirements:
            click.echo(f"Active requirement '{active_req_id}' not found in state.", err=True)
            raise SystemExit(1)

        req = state.requirements[active_req_id]
        click.echo("=" * 40)
        click.echo(f"Active Requirement: {active_req_id} - {req.title}")
        click.echo(f"Current Gate:       {req.current_gate.value}")
        click.echo(f"Status:             {req.status.value}")
        click.echo("-" * 40)
        click.echo("Unlocked Paths:")
        for path in req.unlocked_paths:
            click.echo(f"  - {path}")
        click.echo("=" * 40)
    except GovernanceError as e:
        click.echo(f"[GOVERNANCE ERROR] {e}", err=True)
        raise SystemExit(1) from e


@main.command(name="format-pr-comment")
@click.option("--review-file", required=True, help="Path to gate_review.json")
def format_pr_comment(review_file: str) -> None:
    """Format audit deliverables into PR markdown comments."""
    click.echo(format_audit_comment(review_file))


@main.command(name="format-pr-summary")
@click.option("--decision-file", required=True, help="Path to 05_decision.md/json")
@click.option("--feature-file", required=True, help="Path to acceptance feature file")
def format_pr_summary(decision_file: str, feature_file: str) -> None:
    """Generate Lead Agent PR description digest."""
    click.echo(generate_pr_summary(decision_file, feature_file))


@main.command(name="ci-verify")
@click.pass_context
def ci_verify(ctx: click.Context) -> None:
    """Run headless verification in CI."""
    click.echo("Running CI Verification...")
    ctx.invoke(trace_check)
    click.echo("[GOV] CI Verification Complete.")


@main.command(name="verify-tool")
@click.option("--tool", "-t", default=None, help="Claude Code tool name")
@click.option("--input", "-i", "tool_input", default=None, help="Claude Code tool input JSON")
@click.option("--file", "-f", "target_file", default=None, help="Direct target file path to verify")
def verify_tool(tool: str | None, tool_input: str | None, target_file: str | None) -> None:
    """Verify tool execution against state.json unlocked_paths."""
    if target_file:
        tool_input = json.dumps({"path": target_file})
    if not tool_input:
        return

    try:
        run_verify_tool(tool or DEFAULT_VERIFY_TOOL, tool_input)
    except StateNotFoundError:
        return
    except GovernanceError as e:
        click.echo(f"[GOVERNANCE ERROR] {e}", err=True)
        raise SystemExit(1) from e


@main.command()
@click.option("--gate", required=True, type=str, help="Target gate ID (e.g., gate_1)")
@click.option("--preset", default="SOLO_TOOL", type=str, help="Persona preset to use")
def redteam(gate: str, preset: str) -> None:
    """Run persona audits for the target gate and store review JSONs."""
    try:
        reviews = run_redteam_gate(gate_id=gate, preset=preset)
        click.echo(f"[GOV] Redteam complete. Generated {len(reviews)} reviews for {gate}.")
    except Exception as e:
        click.echo(f"[GOV ERROR] Failed to run redteam: {e}", err=True)
        raise SystemExit(1) from e


@main.command(name="draft-decision")
@click.option("--req", required=True, type=str, help="Requirement ID")
def cmd_draft_decision(req: str) -> None:
    """Generate 05_decision.md containing the Tri-Polar matrix."""
    try:
        draft_decision(requirement_id=req)
        click.echo(f"[GOV] Decision drafted successfully for {req}.")
    except Exception as e:
        click.echo(f"[GOV ERROR] Failed to draft decision: {e}", err=True)
        raise SystemExit(1) from e


@main.command(name="review-status")
@click.option("--gate", required=True, type=str, help="Target gate ID")
def review_status(gate: str) -> None:
    """Summarize persona verdicts and fatal flaw tallies."""
    # For simplicity, load all for now (the requirements typically map to one REQ-ID)
    # We will assume a default requirement ID for demo or a directory check.
    # The requirement specifically mentions "summarize persona verdicts" for a gate.
    # Let's check REQ-000 for standard testing or load from state.
    state_file = Path(".specs/state.json")
    req_id = "REQ-000"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            req_id = data.get("active_requirement_id", "REQ-000")
        except json.JSONDecodeError:
            pass

    reviews = load_reviews(requirement_id=req_id)
    gate_reviews = [r for r in reviews if r.gate_id == gate]

    if not gate_reviews:
        click.echo(f"[GOV] No reviews found for gate: {gate}")
        return

    flaws = sum(len(r.design_flaws) + len(r.test_design_flaws) for r in gate_reviews)
    approved = sum(1 for r in gate_reviews if r.status == "APPROVED")
    total = len(gate_reviews)

    click.echo(f"[GOV] Gate {gate} Review Status:")
    click.echo(f"      Total Reviews: {total}")
    click.echo(f"      Approved: {approved} / {total}")
    click.echo(f"      Total Flaws Identified: {flaws}")


@main.command(name="audit-push")
def audit_push() -> None:
    """Runs local CI validation (pytest with coverage, trace-check)."""
    click.echo("Running local CI validation...")

    try:
        click.echo("Running pytest...")
        subprocess.run([sys.executable, "-m", "pytest"], check=True)

        click.echo("Running trace-check...")
        verify_traceability()

        click.echo("Local CI validation passed.")
    except subprocess.CalledProcessError as e:
        click.echo(f"[GOVERNANCE ERROR] Local CI failed: {e}", err=True)
        raise SystemExit(1) from e
    except GovernanceError as e:
        click.echo(f"[GOVERNANCE ERROR] {e}", err=True)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
