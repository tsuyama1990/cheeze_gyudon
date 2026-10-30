import re
from pathlib import Path

import pytest

AGENT_MD = Path(__file__).parents[2] / "AGENT.md"
BEGIN = "<!-- gov:rules v1 -->"
END = "<!-- /gov:rules -->"
RULE_COUNT = 19
AGENT_PRODUCTS = re.compile(r"claude|anthropic|gemini|antigravity|agy", re.IGNORECASE)


def rules_block() -> str:
    text = AGENT_MD.read_text(encoding="utf-8")
    assert text.count(BEGIN) == 1
    assert text.count(END) == 1
    return text[text.index(BEGIN) : text.index(END)]


@pytest.mark.requirement("REQ-2026-011-F01")
def test_rules_table_has_every_rule_once_in_order() -> None:
    """L1-M05"""
    ids = re.findall(r"^\| (R\d{2}) \|", rules_block(), re.MULTILINE)
    assert ids == [f"R{n:02d}" for n in range(1, RULE_COUNT + 1)]


@pytest.mark.requirement("REQ-2026-011-F01")
def test_rules_table_names_no_agent_product() -> None:
    """L1-M05"""
    assert AGENT_PRODUCTS.findall(rules_block()) == []
