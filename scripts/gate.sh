#!/usr/bin/env bash
set -euo pipefail

echo "========================================================"
echo " Running Full JTC-Gov Local Quality & Governance Suite"
echo "========================================================"

echo "[1/6] Ruff Format & Lint Check..."
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts

echo "[2/6] Mypy Strict Static Type Check..."
uv run mypy src tests

echo "[3/6] Vulture Dead Code Check..."
uv run vulture src --min-confidence 80

echo "[4/6] Duplicate Code Detection..."
uv run python scripts/check_duplicates.py

echo "[5/6] Pytest & Branch Coverage..."
uv run pytest

echo "[6/6] Pre-commit Hooks (All Files)..."
uv run pre-commit run --all-files

echo "========================================================"
echo " [SUCCESS] All Quality Gates & Governance Hooks Passed!"
echo "========================================================"
