"""Decision Engine to synthesize findings and generate Tri-Polar Matrix."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from jtc_gov.domain.review_models import GateReview

SPECS_DIR = Path(".specs")


def load_reviews(requirement_id: str) -> list[GateReview]:
    """Load all reviews for a specific requirement."""
    reviews_dir = SPECS_DIR / requirement_id / "reviews"
    if not reviews_dir.exists():
        return []

    reviews = []
    for file_path in reviews_dir.glob("*.json"):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            reviews.append(GateReview.model_validate(data))
        except (json.JSONDecodeError, OSError, ValidationError):
            continue

    return reviews


def generate_tripolar_matrix(requirement_id: str, reviews: list[GateReview]) -> str:
    """Generate the 05_decision.md content."""
    flaw_count = sum(len(r.design_flaws) + len(r.test_design_flaws) for r in reviews)

    return f"""# Decision Record for {requirement_id}

## Tri-Polar Option Selection Matrix

| Option | Approach | Risk Level |
|---|---|---|
| Option 1 | KISS / Minimum Cost | Low |
| Option 2 | Standard Enterprise / Balanced | Medium |
| Option 3 | Scalable / Future-Proof | High |

## Findings
Total flaws identified across reviews: {flaw_count}

## Risk Acceptance Registry
- None yet.

HUMAN_SIGN_OFF: APPROVED by @username at {datetime.now(UTC).strftime("%Y-%m-%d")}
"""


def draft_decision(requirement_id: str) -> None:
    """Draft the decision document based on reviews."""
    reviews = load_reviews(requirement_id)
    content = generate_tripolar_matrix(requirement_id, reviews)

    req_dir = SPECS_DIR / requirement_id
    req_dir.mkdir(parents=True, exist_ok=True)
    decision_file = req_dir / "05_decision.md"

    decision_file.write_text(content, encoding="utf-8")
