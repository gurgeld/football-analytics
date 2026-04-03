#!/usr/bin/env bash
# Daily football analytics pipeline runner.
# Activates the virtualenv, runs incremental ingestion, dbt build, and dbt docs generate.
# Set VENV_PATH and PROFILES_DIR in your environment or .env file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env if present
if [[ -f "$REPO_ROOT/.env" ]]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

VENV_PATH="${VENV_PATH:-$REPO_ROOT/.venv}"
PROFILES_DIR="${PROFILES_DIR:-$REPO_ROOT/dbt}"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Pipeline started"

# Activate virtualenv
source "$VENV_PATH/bin/activate"

export PYTHONPATH="$REPO_ROOT"

# Step 1: Incremental ingestion
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Running incremental ingestion..."
python -m ingestion.main

# Step 2: dbt build (transformations + tests)
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Running dbt build..."
cd "$REPO_ROOT/dbt"
dbt build --profiles-dir "$PROFILES_DIR"

# Step 3: dbt docs generate
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Generating dbt docs..."
dbt docs generate --profiles-dir "$PROFILES_DIR"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Pipeline complete"
