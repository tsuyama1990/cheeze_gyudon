"""GitHub PR Summary Generator for jtc-gov."""

import json
from pathlib import Path


def extract_decision_info(d_path: Path, lines: list[str]) -> None:
    """Extract decision info into lines."""
    if not d_path.exists():
        lines.append("*(No 05_decision.md/json provided)*\n")
        return

    try:
        d_data = json.loads(d_path.read_text(encoding="utf-8"))
        selected_option = d_data.get("selected_option", "Unknown Option")
        lines.append("### Tri-Polar Option Decision")
        lines.append(f"**Selected Architecture**: {selected_option}")
        rationale = d_data.get("rationale", "")
        if rationale:
            lines.append(f"\n> {rationale}")
        lines.append("")

        consensus = d_data.get("review_persona_consensus", {})
        if consensus:
            lines.append("### Review Persona Consensus")
            for persona, vote in consensus.items():
                icon = "✅" if vote.upper() == "APPROVED" else "❌"
                lines.append(f"- {icon} {persona}")
            lines.append("")

        pending = d_data.get("pending_human_approvals", [])
        if pending:
            lines.append("### ⚠️ Pending Human Approvals")
            lines.extend([f"- [ ] @{approver}" for approver in pending])
            lines.append("")

    except json.JSONDecodeError:
        lines.append("*(Error: Failed to parse decision JSON)*\n")


def extract_feature_info(f_path: Path, lines: list[str]) -> None:
    """Extract feature info into lines."""
    if not f_path.exists():
        return

    try:
        f_content = f_path.read_text(encoding="utf-8")
        criteria_lines = []
        capture = False
        max_lines = 3
        for line in f_content.splitlines():
            clean_line = line.strip()
            if clean_line.startswith(("Feature:", "Scenario:")):
                capture = True
            if capture and clean_line:
                criteria_lines.append(clean_line)
            if len(criteria_lines) >= max_lines:
                break

        if criteria_lines:
            lines.append("### Acceptance Criteria Digest")
            lines.append("```gherkin")
            lines.extend(criteria_lines)
            if len(criteria_lines) == max_lines:
                lines.append("...")
            lines.append("```")
            lines.append("")

    except OSError:
        lines.append("*(Error: Failed to parse feature file)*\n")


def generate_pr_summary(decision_path: str, feature_path: str) -> str:
    """Generate Lead Agent PR description digest from decision and feature files."""
    d_path = Path(decision_path)
    f_path = Path(feature_path)

    lines = ["## Lead Agent (PM-AI) PR Summary\n"]
    extract_decision_info(d_path, lines)
    extract_feature_info(f_path, lines)

    return "\n".join(lines).strip() + "\n"
