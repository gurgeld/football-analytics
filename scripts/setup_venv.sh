#!/usr/bin/env bash
# Create and populate the Python virtualenv. Idempotent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="${VENV_PATH:-$REPO_ROOT/.venv}"

if [[ -d "$VENV_PATH" ]]; then
    echo "Virtualenv already exists at $VENV_PATH"
else
    echo "Creating virtualenv at $VENV_PATH"
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

pip install --upgrade pip --quiet
pip install -r "$REPO_ROOT/requirements.txt" --quiet
pip install -r "$REPO_ROOT/requirements-dev.txt" --quiet

echo "Virtualenv ready: $VENV_PATH"
