#!/usr/bin/env bash
set -euo pipefail

echo "========================================================"
echo " Running Full JTC-Gov Local Quality & Governance Suite"
echo "========================================================"

echo "[1/7] Ruff Format & Lint Check..."
uv run ruff check --fix src tests scripts
uv run ruff format src tests scripts

echo "[2/7] Mypy Strict Static Type Check..."
uv run mypy src tests

echo "[3/7] Vulture Dead Code Eradication Check..."
uv run vulture src --min-confidence 80

echo "[4/7] Duplicate Code Detection..."
uv run python scripts/check_duplicates.py

echo "[5/7] Pytest & Branch Coverage (>= 90%)..."
uv run pytest

echo "[6/7] Staging all files for pre-commit verification..."
git add -A

echo "[7/7] Pre-commit Hooks (All Files)..."
uv run pre-commit run --all-files

echo "========================================================"
echo " [SUCCESS] All Quality Gates & Governance Hooks Passed!"
echo "========================================================"
