# ruff: noqa: PLC0415
"""System Health Diagnostics for jtc-gov."""

import shutil
import sys
import time
from pathlib import Path

import click


def _check_python_version() -> bool:
    """Verify Python version is >= 3.11."""
    py_version = sys.version_info
    if py_version >= (3, 11):
        click.secho(f"  [OK] Python version: {sys.version.split()[0]}", fg="green")
        return True
    click.secho(f"  [FAIL] Python version: {sys.version.split()[0]} (>= 3.11 required)", fg="red")
    return False


def _check_uv_availability() -> bool:
    """Check uv availability in PATH."""
    uv_path = shutil.which("uv")
    if uv_path:
        click.secho(f"  [OK] uv availability: {uv_path}", fg="green")
        return True
    click.secho("  [FAIL] uv availability: uv is not installed or not in PATH", fg="red")
    return False


def _check_git_hooks() -> bool:
    """Inspect Git hooks installation."""
    hooks_dir = Path(".git/hooks")
    if hooks_dir.exists():
        pre_commit = hooks_dir / "pre-commit"
        pre_push = hooks_dir / "pre-push"
        if pre_commit.exists() and pre_push.exists():
            click.secho("  [OK] Git hooks: pre-commit and pre-push active", fg="green")
            return True
        click.secho(
            "  [FAIL] Git hooks: missing pre-commit or pre-push "
            "(run 'uv run pre-commit install --hook-type pre-commit --hook-type pre-push')",
            fg="red",
        )
        return False
    click.secho("  [FAIL] Git hooks: .git/hooks directory not found", fg="red")
    return False


def _check_latency() -> bool:
    """Verify PreToolUse hook execution latency."""
    start_time = time.time()
    try:
        from jtc_gov.services.state_engine import is_path_unlocked

        _ = is_path_unlocked("", [])
        latency = (time.time() - start_time) * 1000
    except Exception as e:  # noqa: BLE001
        click.secho(f"  [FAIL] PreToolUse hook execution failed: {e}", fg="red")
        return False

    max_latency = 50
    if latency < max_latency:
        click.secho(f"  [OK] PreToolUse hook latency: {latency:.2f}ms (<50ms)", fg="green")
        return True
    click.secho(f"  [FAIL] PreToolUse hook latency: {latency:.2f}ms (>=50ms)", fg="red")
    return False


def run_diagnostics() -> None:
    """Diagnose the local governance environment."""
    click.echo("[GOV DOCTOR] Running system health diagnostics...\n")

    results = [
        _check_python_version(),
        _check_uv_availability(),
        _check_git_hooks(),
        _check_latency(),
    ]

    click.echo("\n[GOV DOCTOR] Diagnostic Report Summary:")
    if all(results):
        click.secho("All checks passed. System is healthy.", fg="green", bold=True)
    else:
        click.secho("Some checks failed. Please fix the issues above.", fg="red", bold=True)
        sys.exit(1)
