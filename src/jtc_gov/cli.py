"""Command Line Interface for jtc-gov governance framework."""

import click


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """AI-Driven Development Governance CLI (JTC-Style Governance)."""


@main.command()
def status() -> None:
    """Show current governance state and active gate."""
    click.echo("[GOV] Active gate: GATE1_SPEC (Default initial state)")


if __name__ == "__main__":
    main()
