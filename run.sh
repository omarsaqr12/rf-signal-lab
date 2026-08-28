#!/usr/bin/env bash
# Start the RF Signal Lab on http://127.0.0.1:8765
cd "$(dirname "$0")"
exec python3 -m rflab.server "${1:-8765}"
