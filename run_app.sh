#!/usr/bin/env bash

# Resolve the absolute script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "==================================================="
echo "  ANTS: Analysis of Narrative in Television Seriality"
echo "==================================================="
echo

if command -v python3 >/dev/null 2>&1; then
    python3 "$SCRIPT_DIR/setup.py"
elif command -v python >/dev/null 2>&1; then
    python "$SCRIPT_DIR/setup.py"
else
    echo "[-] Error: Python is not installed or not in PATH."
    echo "Please install Python 3.10+ to run the ANTS framework."
    exit 1
fi
