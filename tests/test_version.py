"""Initial test for jtc_gov package."""

import pytest

from jtc_gov import __version__


@pytest.mark.requirement("REQ-INIT-001")
def test_version() -> None:
    """Verify package version."""
    assert __version__ == "0.1.0"
