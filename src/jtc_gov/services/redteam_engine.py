"""Adversarial Red Teaming Engine for JTC-Gov."""

from datetime import UTC, datetime
from pathlib import Path

from jtc_gov.domain.review_models import GateReview
from jtc_gov.templates.presets import PRESETS

SPECS_DIR = Path(".specs")


def load_persona(persona_name: str) -> str:
    """Load persona markdown file content."""
    template_path = Path(__file__).parent.parent / "templates" / f"{persona_name}.md"
    if not template_path.exists():
        return f"Mock persona for {persona_name}"
    return template_path.read_text(encoding="utf-8")


def mock_evaluate(
    gate_id: str,
    requirement_id: str,
    persona_name: str,
) -> GateReview:
    """Mock evaluation for deterministic red teaming."""
    # Deterministic output based on persona
    if persona_name == "ux_critic":
        flaws = ["Too many clicks required.", "Cluttered interface."]
    elif persona_name == "lazy_senior_dev":
        flaws = ["Re-inventing a standard library feature."]
    else:
        flaws = []

    max_flaws = 2
    return GateReview(
        gate_id=gate_id,
        requirement_id=requirement_id,
        reviewer_persona=persona_name,
        status="APPROVED" if len(flaws) < max_flaws else "REJECTED",
        design_flaws=flaws[:2],
        test_design_flaws=[],
        accepted_tradeoffs=["Accepting minor latency for simplicity."],
        reviewed_at=datetime.now(UTC).isoformat(),
    )


def run_redteam_gate(
    gate_id: str,
    preset: str = "SOLO_TOOL",
    requirement_id: str = "REQ-000",
) -> list[GateReview]:
    """Run red teaming for a specific gate using a preset."""
    if preset not in PRESETS:
        msg = f"Unknown preset: {preset}"
        raise ValueError(msg)

    personas = PRESETS[preset]
    reviews = []

    reviews_dir = SPECS_DIR / requirement_id / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)

    for persona in personas:
        _ = load_persona(persona)
        review = mock_evaluate(gate_id, requirement_id, persona)
        reviews.append(review)

        review_file = reviews_dir / f"{gate_id}_{persona}.json"
        review_file.write_text(
            review.model_dump_json(indent=2),
            encoding="utf-8",
        )

    return reviews
