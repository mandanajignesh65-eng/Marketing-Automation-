#!/bin/bash
# One-time setup: connect Meridian to HeyReach so it can show your LinkedIn campaigns and their results.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -c "import fastapi, uvicorn" 2>/dev/null || .venv/bin/python -m pip install -q -r requirements.txt
exec .venv/bin/python -m meridian.outbound connect heyreach
