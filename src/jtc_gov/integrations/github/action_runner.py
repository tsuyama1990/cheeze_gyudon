"""GitHub Actions Entrypoint for jtc-gov."""

import json
import os
from pathlib import Path

import click


def extract_gate_from_branch(branch_name: str) -> str:
    """Determine gate based on branch name."""
    target_gate = "UNKNOWN"
    if not branch_name:
        return target_gate

    for i in range(1, 6):
        if f"gate{i}" in branch_name:
            target_gate = str(i)
            break

    if target_gate == "UNKNOWN" and "feat/" in branch_name:
        target_gate = "5"

    return target_gate


def run_action() -> int:
    """Read GITHUB_EVENT_PATH, determine target gate based on branch/labels."""
    event_path_str = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path_str:
        click.echo("GITHUB_EVENT_PATH not set.", err=True)
        return 1

    event_path = Path(event_path_str)
    if not event_path.exists():
        click.echo(f"Event payload not found at {event_path}", err=True)
        return 1

    try:
        event_data = json.loads(event_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        click.echo("Failed to parse GITHUB_EVENT_PATH.", err=True)
        return 1

    pull_request = event_data.get("pull_request", {})
    if not pull_request:
        click.echo("Not a pull request event.", err=True)
        return 0

    branch_name = pull_request.get("head", {}).get("ref", "")
    labels = [label.get("name") for label in pull_request.get("labels", [])]

    target_gate = "UNKNOWN"
    for label in labels:
        if isinstance(label, str) and label.startswith("gate:"):
            target_gate = label.split(":", 1)[1]
            break

    if target_gate == "UNKNOWN":
        target_gate = extract_gate_from_branch(branch_name)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as fh:
            fh.write(f"target_gate={target_gate}\n")
    else:
        click.echo(f"::set-output name=target_gate::{target_gate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_action())
