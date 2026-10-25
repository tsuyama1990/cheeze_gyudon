"""Command Line Interface for jtc-gov governance framework."""

import fnmatch
import json
from pathlib import Path

import click

from jtc_gov.services.decision_engine import draft_decision, load_reviews
from jtc_gov.services.redteam_engine import run_redteam_gate


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """AI-Driven Development Governance CLI (JTC-Style Governance)."""


@main.command()
def status() -> None:
    """Show current governance state and active gate."""
    state_file = Path(".specs/state.json")
    if not state_file.exists():
        click.echo("[GOV] No .specs/state.json found. State uninitialized.")
        return

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        req_id = data.get("active_requirement_id", "UNKNOWN")
        req_data = data.get("requirements", {}).get(req_id, {})
        current_gate = req_data.get("current_gate", "UNKNOWN")
        click.echo(f"[GOV] Active Requirement: {req_id} | Gate: {current_gate}")
    except (json.JSONDecodeError, OSError):
        click.echo("[GOV ERROR] Failed to parse .specs/state.json", err=True)


def is_path_unlocked(target_file: str, unlocked_patterns: list[str]) -> bool:
    """Check if target file matches any pattern in unlocked_paths."""
    clean_target = target_file.strip().removeprefix("./").replace("\\", "/")
    for pattern in unlocked_patterns:
        clean_pattern = pattern.strip().removeprefix("./").replace("\\", "/")
        if fnmatch.fnmatch(clean_target, clean_pattern):
            return True
        if clean_pattern.endswith("*") and clean_target.startswith(clean_pattern[:-1]):
            return True
    return False


def extract_target_file(
    tool_input: str | None,
    file_arg: str | None,
) -> str | None:
    """Extract file path from tool input JSON or file argument."""
    if file_arg:
        return file_arg

    if not tool_input:
        return None

    try:
        input_data = json.loads(tool_input)
        if isinstance(input_data, dict):
            for key in ("file_path", "target_file", "path", "file", "TargetFile"):
                val = input_data.get(key)
                if isinstance(val, str):
                    return val
    except json.JSONDecodeError:
        return None
    return None


@main.command(name="verify-tool")
@click.option("--tool", "-t", default=None, help="Claude Code tool name")
@click.option("--input", "-i", "tool_input", default=None, help="Claude Code tool input JSON")
@click.option("--file", "-f", "target_file", default=None, help="Direct target file path to verify")
def verify_tool(tool: str | None, tool_input: str | None, target_file: str | None) -> None:
    """Verify tool execution against state.json unlocked_paths."""
    _ = tool
    file_to_check = extract_target_file(tool_input, target_file)
    if not file_to_check:
        return

    state_file = Path(".specs/state.json")
    if not state_file.exists():
        return

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        req_id = data.get("active_requirement_id", "")
        req_data = data.get("requirements", {}).get(req_id, {})
        unlocked = req_data.get("unlocked_paths", [])

        if not is_path_unlocked(file_to_check, unlocked):
            click.echo(
                f"[GOVERNANCE INTERCEPTION] Access denied: '{file_to_check}' is locked. "
                f"Active gate is '{req_data.get('current_gate')}' for requirement '{req_id}'. "
                f"Unlocked paths: {unlocked}",
                err=True,
            )
            raise SystemExit(1)
    except (json.JSONDecodeError, OSError) as e:
        click.echo(f"[GOVERNANCE ERROR] Failed to verify tool permission: {e}", err=True)
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


if __name__ == "__main__":
    main()
