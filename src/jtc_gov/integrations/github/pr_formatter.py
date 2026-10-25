"""GitHub PR Review Comment Formatter for jtc-gov."""

import json
from pathlib import Path


def format_audit_comment(review_json_path: str) -> str:
    """Format gate_review.json into a GitHub PR markdown comment."""
    path = Path(review_json_path)
    if not path.exists():
        return (
            "## :x: Audit Deliverable Not Found\nNo gate_review.json found at the specified path."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "## :x: Audit Deliverable Parse Error\nFailed to parse gate_review.json."

    gate = data.get("gate", "UNKNOWN")
    persona = data.get("persona", "UNKNOWN")
    status = data.get("status", "REJECTED").upper()

    badge = ":white_check_mark: **APPROVED**" if status == "APPROVED" else ":no_entry: **REJECTED**"

    lines = [
        f"## Governance Audit Report - {gate}",
        f"**Persona**: {persona} | **Status**: {badge}",
        "",
    ]

    flaws = data.get("fatal_flaws", [])
    if flaws:
        lines.append("### :warning: Fatal Flaws Detected")
        lines.append("| ID | Severity | Description | Action Required |")
        lines.append("|:---|:---------|:------------|:----------------|")
        for flaw in flaws:
            fid = flaw.get("id", "-")
            sev = flaw.get("severity", "HIGH")
            desc = flaw.get("description", "-").replace("\n", " ")
            action = flaw.get("action_required", "-").replace("\n", " ")
            lines.append(f"| {fid} | {sev} | {desc} | {action} |")
        lines.append("")
    else:
        lines.append("### :sparkles: No Fatal Flaws Detected")
        lines.append("")

    tradeoffs = data.get("accepted_tradeoffs", [])
    if tradeoffs:
        lines.append("### :balance_scale: Accepted Trade-offs")
        lines.extend([f"- {trade}" for trade in tradeoffs])
        lines.append("")

    return "\n".join(lines).strip() + "\n"
