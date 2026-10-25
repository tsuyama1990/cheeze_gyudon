"""Preset configurations for red teaming personas."""

from typing import Final

PRESETS: Final[dict[str, list[str]]] = {
    "SOLO_TOOL": ["ux_critic", "lazy_senior_dev", "finops_sec_lite"],
    "STARTUP_SAAS": ["cpo", "tech_lead", "sre_sec"],
    "ENTERPRISE_JTC": ["legal", "finance", "cpo", "coo"],
}
