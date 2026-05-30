#!/bin/bash
# Run ClubLedger – creates a virtualenv if needed, ensures deps are installed, starts the server.
set -e

VENV=".venv"

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install --quiet -r requirements.txt

exec "$VENV/bin/python" main.py "$@"
