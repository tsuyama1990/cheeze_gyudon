#!/usr/bin/env bash
set -euo pipefail

BASE="${GATE_BASE:-origin/main}"
THRESHOLD="$(uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['tool']['coverage']['report']['fail_under'])")"

echo "[1/7] Ruff lint & format..."
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts

echo "[2/7] Mypy..."
uv run mypy src tests

echo "[3/7] Vulture..."
uv run vulture

echo "[4/7] Pytest & coverage..."
uv run pytest

echo "[5/7] Changed-line coverage vs ${BASE}..."
uv run diff-cover coverage.xml --compare-branch="${BASE}" --fail-under="${THRESHOLD}"

echo "[6/7] gov check vs ${BASE}..."
uv run gov check --base "${BASE}"

echo "[7/7] Pre-commit hygiene (all files)..."
uv run pre-commit run --all-files

echo "[SUCCESS] All quality gates passed."
