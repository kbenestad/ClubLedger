#!/bin/bash
# Run ClubLedger – creates a virtualenv on first run, then starts the server.
set -e

VENV=".venv"

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
    echo "Installing dependencies..."
    "$VENV/bin/pip" install --quiet -r requirements.txt
    echo "Done."
fi

exec "$VENV/bin/python" main.py "$@"
